from django.shortcuts import render


from silvereye.models import PublisherMetrics


def home(request):
    return render(request, "silvereye/publisher_hub_home.html", {})


def publisher_listing(request):
    return render(request, "silvereye/publisher_listing.html", {})


def publisher(request):
    return render(request, "silvereye/publisher.html")


# TODO: Remove this once we've moved the styles over to cove-ocds's main upload form.
def upload_results(request):
    return render(request, "silvereye/upload_results.html")
