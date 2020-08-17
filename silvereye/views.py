from datetime import datetime, timedelta
from django.db.models import Count, Max, F

from cove.input.models import SuppliedData
from cove.input.views import data_input
from django.shortcuts import render

from bluetail.models import OCDSPackageData
from silvereye.models import PublisherMetrics, Publisher


def home(request):
    # Get supplieddata that have releated OCDS Json packages
    valid_submissions = SuppliedData.objects.filter(ocdspackagedata__publisher_name__isnull=False).distinct()
    recent_submissions = valid_submissions.order_by("-created")[:10]
    packages = OCDSPackageData.objects.all()

    context = {
            "packages": packages,
        "recent_submissions": recent_submissions
    }
    return render(request, "silvereye/publisher_hub_home.html", context)


def publisher_listing(request):
    # packages = OCDSPackageData.objects.all()
    # sorted_packages = packages.order_by("publisher_name", "-supplied_data__created")
    # distinct = sorted_packages.distinct("publisher_name")

    publishers = OCDSPackageData.objects.all()\
        .values('publisher_name')\
        .order_by('-supplied_data__created')\
        .annotate(last_submission=Max("supplied_data__created")) \
        .annotate(total=Count('publisher_name'))\
        .order_by('publisher_name') \

    context = {
        'publishers': publishers,
        # 'publisher_metrics': PublisherMetrics.objects.all(),
        "submission_date_yellow": datetime.today() - timedelta(days=14),
        "submission_date_red": datetime.today() - timedelta(days=30),
    }
    return render(request, "silvereye/publisher_listing.html", context)


def publisher(request, publisher_name):
    valid_submissions = SuppliedData.objects.filter(ocdspackagedata__publisher_name__isnull=False).distinct()
    recent_submissions = valid_submissions.filter(ocdspackagedata__publisher_name=publisher_name).order_by("-created")[:10]
    publisher = {
        "publisher_name": publisher_name
    }
    publisher_metrics = PublisherMetrics.objects.filter(publisher_id=publisher_name).first()
    packages = OCDSPackageData.objects.filter(publisher_name=publisher_name)

    publisher_metadata = Publisher.objects.filter(publisher_name=publisher_name)
    if publisher_metadata:
        publisher_metadata = publisher_metadata[0]

    context = {
        "recent_submissions": recent_submissions,
        'publisher': publisher,
        'publisher_metadata': publisher_metadata,
        'packages': packages,
        'publisher_metrics': publisher_metrics,
    }
    return render(request, "silvereye/publisher.html", context)


# TODO: Remove this once we've moved the styles over to cove-ocds's main upload form.
def upload_results(request):
    return render(request, "silvereye/upload_results.html")


def custom_data_input(request, *args, **kwargs):
    # Add something to request.POST so data_input doesn't ignore uploaded files.
    request.POST = request.POST.copy()
    request.POST["something"] = "Dummy POSST content so the CSV gets processed"
    return data_input(request, *args, **kwargs)
