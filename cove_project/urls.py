from datetime import datetime

from cove.urls import handler500  # noqa: F401
from cove.urls import urlpatterns as urlpatterns_core
from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.views.generic import RedirectView
from cove.input.views import data_input

import cove_ocds.views
# from cove_ocds.input.views import data_input


# Serve the OCDS validator at /validator/
urlpatterns = [
    url(r"^$", RedirectView.as_view(url="review/", permanent=False)),
    url(r'^review/$', data_input,
        kwargs={
            "text_file_name": "{}.json".format(datetime.now().strftime("%Y%m%dT%H%M%SZ"))
        },
        name='index'),
    url(r"^review/", include(urlpatterns_core)),
    url(r"^data/(.+)$", cove_ocds.views.explore_ocds, name="explore")
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
