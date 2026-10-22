from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .kenya_counties import official_county_number
from .models import GeographicIndicator, GeographicPlace


def published(place_code=None):
    # No enquiry records or person-level geographic records are public.
    query = (GeographicIndicator.objects
             .filter(source__approved_for_publication=True)
             .select_related("source", "place")
             .order_by("-period", "place__name", "indicator"))
    if place_code:
        query = query.filter(place__code=place_code)
    return query[:100]


@require_GET
def dashboard(request):
    return render(request, "analytics/dashboard.html", {
        "rows": published(request.GET.get("place", "")[:80])
    })


@require_GET
def indicator_api(request):
    rows = [{
        "place_code": row.place.code,
        "place": row.place.name,
        "place_type": row.place.place_type,
        "place_path": row.place.label_path,
        "indicator": row.indicator,
        "period": row.period.isoformat(),
        "value": str(row.value),
        "unit": row.unit,
        "publisher": row.source.publisher,
        "source": row.source.name,
        "last_imported_at": (
            row.source.last_imported_at.isoformat()
            if row.source.last_imported_at else None
        ),
    } for row in published(request.GET.get("place", "")[:80])]
    response = JsonResponse({"count": len(rows), "results": rows})
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def places_api(request):
    parent_code = request.GET.get("parent", "")[:80]
    if parent_code:
        queryset = GeographicPlace.objects.filter(parent__code=parent_code)
    else:
        queryset = GeographicPlace.objects.filter(
            parent__isnull=True, place_type=GeographicPlace.COUNTRY
        )
    records = list(queryset.select_related("parent").order_by("name", "code")[:300])

    # Kenyan official county numbers (001–047) differ from ISO 3166-2 keys.
    # Sort/display by the official number without changing stored place codes.
    if parent_code == "KE":
        records.sort(key=lambda place: (
            int(official_county_number(place.name) or "999")
            if place.place_type == "county" else 1000,
            place.name, place.code,
        ))

    places = []
    for place in records:
        county_number = (
            official_county_number(place.name)
            if parent_code == "KE" and place.place_type == "county" else None
        )
        places.append({
            "code": place.code,
            "name": place.name,
            "display_name": (
                f"{county_number} — {place.name}" if county_number else place.name
            ),
            "county_number": county_number,
            "place_type": place.place_type,
            "parent_code": place.parent.code if place.parent_id else None,
        })
    return JsonResponse({"count": len(places), "results": places})
