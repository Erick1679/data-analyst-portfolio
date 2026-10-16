from django.contrib import admin
from django.urls import path
from analytics import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.dashboard, name="dashboard"),
    path("api/indicators/", views.indicator_api, name="indicator-api"),
    path("api/places/", views.places_api, name="places-api"),
]
