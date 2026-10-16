from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from .models import CountyIndicator


def published():
    return (CountyIndicator.objects
            .filter(source__approved_for_publication=True)
            .select_related("source")
            .order_by("-period", "county", "indicator")[:100])


@require_GET
def dashboard(request):
    return render(request, "analytics/dashboard.html", {"rows": published()})


@require_GET
def indicator_api(request):
    # No client enquiries or personal data are ever exposed by this endpoint.
    rows = [{
        "county": item.county, "indicator": item.indicator,
        "period": item.period.isoformat(), "value": str(item.value),
        "unit": item.unit, "publisher": item.source.publisher,
        "source": item.source.name,
        "last_imported_at": (item.source.last_imported_at.isoformat()
                             if item.source.last_imported_at else None),
    } for item in published()]
    response = JsonResponse({"count": len(rows), "results": rows})
    response["Cache-Control"] = "no-store"
    return response
