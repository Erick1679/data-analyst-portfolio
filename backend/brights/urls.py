from django.contrib import admin
from django.urls import path
from analytics import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.dashboard, name="dashboard"),
    path("api/county-indicators/", views.indicator_api, name="indicator-api"),
]
