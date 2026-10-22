from django.contrib import admin

from .models import (
    ClientEnquiry, DataSource, GeographicIndicator, GeographicPlace,
    LocalAuthority, Project
)


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = (
        "name", "publisher", "approved_for_publication",
        "approved_for_commercial_use", "last_imported_at",
    )
    list_filter = ("approved_for_publication", "approved_for_commercial_use")
    search_fields = ("name", "publisher")


@admin.register(GeographicPlace)
class GeographicPlaceAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "place_type", "parent", "data_source")
    list_filter = ("place_type",)
    search_fields = ("name", "code")
    autocomplete_fields = ("parent", "data_source")


@admin.register(LocalAuthority)
class LocalAuthorityAdmin(admin.ModelAdmin):
    list_display = (
        "name", "country", "authority_type", "verification_status",
        "jurisdiction", "source",
    )
    list_filter = ("country", "authority_type", "verification_status")
    search_fields = ("name", "country__name", "jurisdiction__name")
    autocomplete_fields = ("country", "jurisdiction", "source")
    fieldsets = (
        ("Local authority", {
            "fields": ("name", "country", "authority_type"),
        }),
        ("Source and verification", {
            "fields": ("source", "verification_status", "notes"),
        }),
        ("Geographic jurisdiction (optional)", {
            "fields": ("jurisdiction",),
            "description": (
                "A council is an institution. Do not guess its boundaries "
                "or link it to a place until that relationship is verified."
            ),
        }),
    )


@admin.register(GeographicIndicator)
class GeographicIndicatorAdmin(admin.ModelAdmin):
    list_display = ("place", "indicator", "value", "unit", "period", "source")
    list_filter = ("source", "place__place_type")
    search_fields = ("indicator", "place__name", "place__code")
    autocomplete_fields = ("place", "source")


@admin.register(ClientEnquiry)
class ClientEnquiryAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "place", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "email")
    autocomplete_fields = ("place",)
    readonly_fields = ("created_at",)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "due_date")
    list_filter = ("status",)
