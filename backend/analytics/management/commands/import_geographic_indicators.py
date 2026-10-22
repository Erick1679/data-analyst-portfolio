"""Import authorised aggregate indicators for any place in the hierarchy."""
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from analytics.models import DataSource, GeographicIndicator, GeographicPlace


class Command(BaseCommand):
    help = "Import place_code,indicator,period,value[,unit] CSV observations."

    def add_arguments(self, parser):
        parser.add_argument("file", type=Path)
        parser.add_argument("--source-id", type=int, required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            source = DataSource.objects.get(pk=options["source_id"])
        except DataSource.DoesNotExist as exc:
            raise CommandError("Create a DataSource in admin before importing.") from exc
        if not source.publisher.strip() or not source.licence_notes.strip():
            raise CommandError("Publisher and licence notes are required.")
        count = 0
        try:
            with options["file"].open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames or not {
                    "place_code", "indicator", "period", "value"
                }.issubset(reader.fieldnames):
                    raise CommandError(
                        "Required columns: place_code,indicator,period,value"
                    )
                for line, row in enumerate(reader, 2):
                    try:
                        place_code = row["place_code"].strip()
                        place = GeographicPlace.objects.get(code=place_code)
                        indicator = row["indicator"].strip()
                        period = date.fromisoformat(row["period"].strip())
                        value = Decimal(row["value"].strip())
                        unit = (row.get("unit") or "").strip()
                        if not indicator or not value.is_finite():
                            raise ValueError("Empty indicator or non-finite value")
                        if len(indicator) > 160 or len(unit) > 50:
                            raise ValueError("Text field too long")
                    except GeographicPlace.DoesNotExist as exc:
                        raise CommandError(
                            f"Row {line}: unknown place_code {place_code!r}."
                        ) from exc
                    except (KeyError, AttributeError, ValueError, InvalidOperation) as exc:
                        raise CommandError(f"Row {line}: invalid row: {exc}") from exc
                    GeographicIndicator.objects.update_or_create(
                        source=source, place=place, indicator=indicator, period=period,
                        defaults={"value": value, "unit": unit},
                    )
                    count += 1
        except OSError as exc:
            raise CommandError(f"Cannot open indicator CSV: {exc}") from exc
        source.last_imported_at = timezone.now()
        source.save(update_fields=["last_imported_at"])
        self.stdout.write(self.style.SUCCESS(
            f"Imported {count} aggregate observations. Publication remains approval-gated."
        ))
