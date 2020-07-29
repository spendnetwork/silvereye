from django.urls import include, path, reverse_lazy
from django.contrib import admin
from django.views.generic import RedirectView

import silvereye.views as views

urlpatterns = [
    path('', views.home, name='publisher-hub'),
    path('publishers/all/', views.publisher_listing, name='publisher-listing'),
    path('publisher/', views.publisher, name='publisher'),
    path('upload-results/', views.upload_results, name='upload-results'),
]
