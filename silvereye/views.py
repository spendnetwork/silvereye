from datetime import datetime, timedelta

import requests
from django import forms
from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Count, Max, F, Sum
from django.db.models.functions import ExtractMonth, ExtractDay, ExtractYear, Coalesce

from cove.input.models import SuppliedData
from django.shortcuts import render, redirect
from django.utils.translation import ugettext_lazy as _

from bluetail.models import OCDSPackageData, OCDSReleaseView
from silvereye.helpers import get_published_release_metrics, MetricHelpers
from silvereye.models import PublisherMetrics, Publisher, FileSubmission, PublisherMonthlyCounts


def home(request):
    # Get FileSubmission that have releated OCDS Json packages
    valid_submissions = FileSubmission.objects.filter(ocdspackagedata__publisher_name__isnull=False).distinct()
    recent_submissions = valid_submissions.order_by("-created")[:10]
    packages = OCDSPackageData.objects.all()

    period_option = request.GET.get('period', '1_month') or '1_month'
    comparison_option = request.GET.get('comparison', 'preceding') or 'preceding'

    # metrics from helper
    publisher_metrics = PublisherMonthlyCounts.objects.all()
    metrics = get_publisher_metrics_context(queryset=publisher_metrics, period_option=period_option, comparison_option=comparison_option)
    context = {
        "packages": packages,
        "recent_submissions": recent_submissions,
        "publisher_metrics": metrics,
    }
    return render(request, "silvereye/publisher_hub_home.html", context)


def publisher_listing(request):
    # packages = OCDSPackageData.objects.all()
    # sorted_packages = packages.order_by("publisher_name", "-supplied_data__created")
    # distinct = sorted_packages.distinct("publisher_name")

    publishers = OCDSPackageData.objects.all() \
        .values('publisher_name') \
        .order_by('-supplied_data__created') \
        .annotate(last_submission=Max("supplied_data__created")) \
        .annotate(total=Count('publisher_name')) \
        .order_by('publisher_name') \

    context = {
        'publishers': publishers,
        # 'publisher_metrics': PublisherMetrics.objects.all(),
        "submission_date_yellow": datetime.today() - timedelta(days=14),
        "submission_date_red": datetime.today() - timedelta(days=30),
    }
    return render(request, "silvereye/publisher_listing.html", context)

def get_publisher_metrics_context(queryset=None, period_option='1_month', comparison_option='preceding'):
    if not queryset:
        return {}

    today = datetime.now().date()
    metric_helpers = MetricHelpers()
    context = metric_helpers.metric_data(queryset=queryset,
                                              reference_date=today,
                                              period_option=period_option,
                                              comparison_option=comparison_option)
    context["period_option"] = metric_helpers.period_descriptions()[period_option]
    context["comparison_option"] = metric_helpers.comparison_descriptions()[comparison_option]
    return context


def publisher(request, publisher_name):
    valid_submissions = FileSubmission.objects.filter(ocdspackagedata__publisher_name__isnull=False).distinct()
    recent_submissions = valid_submissions.filter(ocdspackagedata__publisher_name=publisher_name).order_by("-created")[
                         :10]
    publisher = {
        "publisher_name": publisher_name
    }

    packages = OCDSPackageData.objects.filter(publisher_name=publisher_name)

    # metrics from cached model
    publisher_metrics = PublisherMetrics.objects.filter(publisher_id=publisher_name).first()

    publisher_metadata = Publisher.objects.filter(publisher_name=publisher_name)
    if publisher_metadata:
        publisher_metadata = publisher_metadata[0]

    # metrics from helper
    publisher_metrics = PublisherMonthlyCounts.objects.filter(publisher__publisher_name=publisher_name)
    metrics = get_publisher_metrics_context(publisher_metrics, period_option=period_option, comparison_option=comparison_option)

    poor_performers = None

    context = {
        "recent_submissions": recent_submissions,
        'publisher': publisher,

        'publisher_metadata': publisher_metadata,
        'packages': packages,
        # 'publisher_metrics': publisher_metrics,
        'publisher_metrics': metrics,
    }
    return render(request, "silvereye/publisher.html", context)


# TODO: Remove this once we've moved the styles over to cove-ocds's main upload form.
def upload_results(request):
    return render(request, "silvereye/upload_results.html")


class UploadForm(forms.ModelForm):
    publisher_id = forms.ModelChoiceField(label=_('Select a publisher'), queryset=Publisher.objects.all())

    class Meta:
        model = FileSubmission
        fields = ["publisher_id", 'original_file']
        labels = {
            'original_file': _('Upload a file (.json, .csv, .xlsx, .ods)')
        }


class UrlForm(forms.ModelForm):
    publisher_id = forms.ModelChoiceField(queryset=Publisher.objects.all())

    class Meta:
        model = FileSubmission
        fields = ["publisher_id", 'source_url']
        labels = {
            'source_url': _('Supply a URL')
        }


class TextForm(forms.Form):
    publisher_id = forms.ModelChoiceField(label=_('Select a publisher'), queryset=Publisher.objects.all())
    paste = forms.CharField(label=_('Paste (JSON only)'), widget=forms.Textarea)


default_form_classes = {
    'upload_form': UploadForm,
    'url_form': UrlForm,
    'text_form': TextForm,
}


def data_input(request, *args, **kwargs):
    form_classes = default_form_classes
    text_file_name = 'test.json'
    # Add something to request.POST so data_input doesn't ignore uploaded files.
    request.POST = request.POST.copy()
    request.POST["something"] = "Dummy POST content so the CSV gets processed when CSRF not present"
    forms = {form_name: form_class() for form_name, form_class in form_classes.items()}
    request_data = None
    if "source_url" in request.GET:
        request_data = request.GET
    if request.POST:
        request_data = request.POST
    if request_data:
        if 'source_url' in request_data:
            form_name = 'url_form'
        elif 'paste' in request_data:
            form_name = 'text_form'
        else:
            form_name = 'upload_form'
        form = form_classes[form_name](request_data, request.FILES)
        forms[form_name] = form
        if form.is_valid():
            if form_name == 'text_form':
                data = FileSubmission()
            else:
                # pk assigned manually as it does not get set on initial Form submission
                # but is needed for SuppliedData.original_file.upload_to()
                form.instance.pk = form.instance.id
                data = form.save(commit=False)
            data.current_app = request.current_app
            data.form_name = form_name
            data.save()
            data.publisher_id = form.cleaned_data['publisher_id']
            data.save()
            if form_name == 'url_form':
                try:
                    data.download()
                except requests.ConnectionError as err:
                    return render(request, 'error.html', context={
                        'sub_title': _("Sorry we got a ConnectionError whilst trying to download that file"),
                        'link': 'index',
                        'link_text': _('Try Again'),
                        'msg': _(str(err) + '\n\n Common reasons for this error include supplying a local '
                                            'development url that our servers can\'t access, or misconfigured SSL certificates.')
                    })
                except requests.HTTPError as err:
                    return render(request, 'error.html', context={
                        'sub_title': _("Sorry we got a HTTP Error whilst trying to download that file"),
                        'link': 'index',
                        'link_text': _('Try Again'),
                        'msg': _(str(err) + '\n\n If you can access the file through a browser then the problem '
                                            'may be related to permissions, or you may be blocking certain user agents.')
                    })
            elif form_name == 'text_form':
                data.original_file.save(text_file_name, ContentFile(form['paste'].value()))
            return redirect(data.get_absolute_url())

    return render(request, settings.COVE_CONFIG.get('input_template', 'input.html'), {'forms': forms})
