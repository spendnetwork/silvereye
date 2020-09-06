from datetime import datetime, timedelta

import requests
from django import forms
from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Count, Max, F, IntegerField
from django.db.models.functions import ExtractDay, Cast, TruncDate, Now
from django.http import HttpResponse

from django.shortcuts import render, redirect
from django.utils.translation import ugettext_lazy as _

from bluetail.models import OCDSPackageData
from silvereye.helpers import get_publisher_metrics_context, \
    get_coverage_metrics_context, get_metric_options
from silvereye.models import Publisher, FileSubmission, PublisherMonthlyCounts, FieldCoverage, AuthorityType
from silvereye.ocds_csv_mapper import CSVMapper


def home(request):
    # Get FileSubmission that have releated OCDS Json packages
    valid_submissions = FileSubmission.objects.filter(ocdspackagedata__publisher_name__isnull=False).distinct()
    recent_submissions = valid_submissions.order_by("-created")[:10]
    packages = OCDSPackageData.objects.all()

    period_option, comparison_option = get_metric_options(request)
    # metrics from helper
    publisher_metrics = PublisherMonthlyCounts.objects.all()
    metrics = get_publisher_metrics_context(queryset=publisher_metrics, period_option=period_option, comparison_option=comparison_option)

    coverage_metrics = FieldCoverage.objects.all()
    coverage_metrics_context = get_coverage_metrics_context(coverage_metrics, period_option=period_option, comparison_option=comparison_option)

    publishers = Publisher.objects.all() \
        .annotate(last_submission=Max("filesubmission__created")) \
        .annotate(age=Cast(ExtractDay(TruncDate(Now()) - TruncDate(F('last_submission'))), IntegerField())) \
        .order_by('-age') \

    context = {
        "packages": packages,
        "recent_submissions": recent_submissions,
        "publisher_metrics": metrics,
        'coverage_metrics': coverage_metrics_context,
        "publishers": publishers[:5],
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
        .order_by('publisher_name')

    local_authority_name_to_type = {at.authority_name: at.authority_type for at in AuthorityType.objects.all()}
    for publisher in publishers:
        publisher['type'] = local_authority_name_to_type.get(publisher['publisher_name'], "Other")

    filter_authority_types = request.GET.getlist('authority_type')
    if filter_authority_types:
        publishers = filter(lambda x: x['type'] in filter_authority_types, publishers)

    unique_authority_types = AuthorityType.objects \
        .exclude(authority_type='') \
        .distinct('authority_type') \
        .order_by('authority_type') \
        .values_list('authority_type', flat=True)

    known_types = [(kt, kt in filter_authority_types) for kt in unique_authority_types]
    known_types.extend([("Other", "Other" in filter_authority_types)])

    context = {
        'publishers': publishers,
        # 'publisher_metrics': PublisherMetrics.objects.all(),
        "submission_date_yellow": datetime.today() - timedelta(days=14),
        "submission_date_red": datetime.today() - timedelta(days=30),
        "known_types": known_types,
    }
    return render(request, "silvereye/publisher_listing.html", context)


def publisher(request, publisher_name):
    valid_submissions = FileSubmission.objects.filter(ocdspackagedata__publisher_name__isnull=False).distinct()
    recent_submissions = valid_submissions.filter(ocdspackagedata__publisher_name=publisher_name).order_by("-created")[
                         :10]

    packages = OCDSPackageData.objects.filter(publisher_name=publisher_name)

    publisher = Publisher.objects.get(publisher_name=publisher_name)

    # metrics from cached model
    # publisher_metrics = PublisherMetrics.objects.filter(publisher_id=publisher_name).first()

    # metrics from helper
    publisher_metrics = PublisherMonthlyCounts.objects.filter(publisher__publisher_name=publisher_name)
    period_option, comparison_option = get_metric_options(request)
    metrics = get_publisher_metrics_context(publisher_metrics, period_option=period_option, comparison_option=comparison_option)

    coverage_metrics = FieldCoverage.objects.filter(file_submission__publisher__publisher_name=publisher_name)
    coverage_metrics_context = get_coverage_metrics_context(coverage_metrics, period_option=period_option, comparison_option=comparison_option)

    context = {
        "recent_submissions": recent_submissions,
        'packages': packages,
        'publisher': publisher,
        'publisher_metrics': metrics,
        'coverage_metrics': coverage_metrics_context,
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
    try:
        publisher = Publisher.objects.get(publisher_name=request.GET.get("publisher"))
    except Publisher.DoesNotExist:
        publisher = None
    forms = {form_name: form_class(initial={'publisher_id': publisher}) for form_name, form_class in form_classes.items()}
    request_data = None
    if "source_url" in request.GET:
        request_data = request.GET
    if request.POST or request.FILES:
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


def download_csv_template(request, notice_type="tender"):
   response = HttpResponse(content_type='text/csv')
   filename = f"{notice_type}_template.csv"
   response['Content-Disposition'] = u'attachment; filename="{0}"'.format(filename)
   CSVMapper().create_simple_csv_template(response, release_type=notice_type)

   return response