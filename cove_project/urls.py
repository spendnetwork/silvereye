from datetime import datetime

from cove.urls import handler500  # noqa: F401
from cove.urls import urlpatterns as urlpatterns_core
from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.urls import include, path

import cove_ocds.views

# Serve the OCDS validator at /validator/
from silvereye.views import data_input

urlpatterns = [
    url(r"^$", RedirectView.as_view(url="review/", permanent=False)),
    url(r"^admin/$", RedirectView.as_view(url="/review/admin/", permanent=False)),
    url(r'^review/$', data_input,
        kwargs={
            "text_file_name": "{}.json".format(datetime.now().strftime("%Y%m%dT%H%M%SZ"))
        },
        name='index'),
    url(r"^review/", include(urlpatterns_core)),
    url(r"^data/(.+)$", cove_ocds.views.explore_ocds, name="explore"),
    path(r'', include('bluetail.urls')),
    path('publisher-hub/', include('silvereye.urls')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
