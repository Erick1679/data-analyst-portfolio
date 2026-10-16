from django.contrib import admin
from .models import DataSource, CountyIndicator, ClientEnquiry, Project

@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "publisher", "approved_for_publication",
                    "approved_for_commercial_use", "last_imported_at")
    list_filter = ("approved_for_publication", "approved_for_commercial_use")

@admin.register(CountyIndicator)
class IndicatorAdmin(admin.ModelAdmin):
    list_display = ("county", "indicator", "value", "unit", "period", "source")
    list_filter = ("county", "source")
    search_fields = ("county", "indicator")

@admin.register(ClientEnquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "county", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "email")
    readonly_fields = ("created_at",)

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "due_date")
    list_filter = ("status",)
