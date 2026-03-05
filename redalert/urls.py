from django.contrib import admin
from django.urls import include, path

from alerts.views import dashboard, map_lab

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("map-lab/", map_lab, name="map-lab"),
    path("admin/", admin.site.urls),
    path("api/", include("alerts.urls")),
]
