"""Import a licensed aggregate dataset from a local CSV file, never contact lists."""
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from analytics.models import DataSource, CountyIndicator


class Command(BaseCommand):
    help = "Import county,indicator,period,value[,unit] CSV into a reviewed source."

    def add_arguments(self, parser):
        parser.add_argument("file", type=Path)
        parser.add_argument("--source-id", type=int, required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            source = DataSource.objects.get(pk=options["source_id"])
        except DataSource.DoesNotExist as error:
            raise CommandError("Create a source in /admin/ first.") from error
        if not source.publisher.strip() or not source.licence_notes.strip():
            raise CommandError("Publisher and licence notes must be recorded.")
        try:
            with options["file"].open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                if not reader.fieldnames or not {
                    "county", "indicator", "period", "value"
                }.issubset(reader.fieldnames):
                    raise CommandError("Required columns: county,indicator,period,value")
                count = 0
                for line_no, row in enumerate(reader, 2):
                    try:
                        county = row["county"].strip()
                        indicator = row["indicator"].strip()
                        period = date.fromisoformat(row["period"].strip())
                        value = Decimal(row["value"].strip())
                        unit = (row.get("unit") or "").strip()
                        if not county or not indicator or not value.is_finite():
                            raise ValueError("Empty or non-finite field")
                        if len(county) > 100 or len(indicator) > 160 or len(unit) > 50:
                            raise ValueError("Field too long")
                    except (AttributeError, KeyError, ValueError, InvalidOperation) as e:
                        raise CommandError(f"Invalid line {line_no}: {e}") from e
                    CountyIndicator.objects.update_or_create(
                        source=source, county=county, indicator=indicator, period=period,
                        defaults={"value": value, "unit": unit},
                    )
                    count += 1
        except OSError as error:
            raise CommandError(f"Cannot read CSV: {error}") from error
        source.last_imported_at = timezone.now()
        source.save(update_fields=["last_imported_at"])
        self.stdout.write(self.style.SUCCESS(
            f"Imported {count} aggregate records. Publication is still approval-gated."
        ))
