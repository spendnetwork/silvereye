from django.shortcuts import render


from silvereye.models import PublisherMetrics


def home(request):
    return render(request, "silvereye/publisher_hub_home.html", {})


def publisher_listing(request):
    context = {
        'publishers': PublisherMetrics.objects.all(),
    }
    return render(request, "silvereye/publisher_listing.html", context)


def publisher(request, publisher_id):
    context = {
        'publisher': PublisherMetrics.objects.get(publisher_id=publisher_id),
    }
    return render(request, "silvereye/publisher.html", context)


# TODO: Remove this once we've moved the styles over to cove-ocds's main upload form.
def upload_results(request):
    return render(request, "silvereye/upload_results.html")
