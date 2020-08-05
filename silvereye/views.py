from cove.input.models import SuppliedData
from cove.input.views import data_input
from django.shortcuts import render

from bluetail.models import OCDSPackageData
from silvereye.models import PublisherMetrics


def home(request):
    # Get supplieddata that have releated OCDS Json packages
    valid_submissions = SuppliedData.objects.filter(ocdspackagedata__publisher_name__isnull=False).distinct()
    recent_submissions = valid_submissions.order_by("-created")[:10]
    context = {
        "recent_submissions": recent_submissions
    }
    return render(request, "silvereye/publisher_hub_home.html", context)


def publisher_listing(request):
    packages = OCDSPackageData.objects.all()
    sorted_packages = packages.order_by("publisher_name", "-supplied_data__created")
    distinct = sorted_packages.distinct("publisher_name")

    context = {
        'packages': distinct,
        'publishers': PublisherMetrics.objects.all(),
    }
    return render(request, "silvereye/publisher_listing.html", context)


def publisher(request, publisher_name):
    valid_submissions = SuppliedData.objects.filter(ocdspackagedata__publisher_name__isnull=False).distinct()
    recent_submissions = valid_submissions.filter(ocdspackagedata__publisher_name=publisher_name).order_by("-created")[:10]
    publisher = {
        "publisher_name": publisher_name
    }
    publisher_metrics = PublisherMetrics.objects.filter(publisher_id=publisher_name).first()
    context = {
        "recent_submissions": recent_submissions,
        'publisher': publisher,
        'publisher_metrics': publisher_metrics,
    }
    return render(request, "silvereye/publisher.html", context)


# TODO: Remove this once we've moved the styles over to cove-ocds's main upload form.
def upload_results(request):
    return render(request, "silvereye/upload_results.html")
