"""Import vetted geographic reference records in parent-first order.

Columns: code,name,place_type,parent_code; parent_code blank for countries.
Codes must be stable and globally unique. No external scraping is performed.
"""
import csv
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from analytics.models import DataSource, GeographicPlace


class Command(BaseCommand):
    help = "Import a licensed hierarchy of countries, states, regions, counties and cities."

    def add_arguments(self, parser):
        parser.add_argument("file", type=Path)
        parser.add_argument("--source-id", type=int, required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            source = DataSource.objects.get(pk=options["source_id"])
        except DataSource.DoesNotExist as exc:
            raise CommandError("Create a geographical DataSource in the admin first.") from exc
        if not source.licence_notes.strip() or not source.publisher.strip():
            raise CommandError("Record publisher and licence notes before importing.")
        count = 0
        try:
            with options["file"].open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames or not {
                    "code", "name", "place_type", "parent_code"
                }.issubset(reader.fieldnames):
                    raise CommandError(
                        "Expected columns: code,name,place_type,parent_code"
                    )
                for line, row in enumerate(reader, 2):
                    code = (row.get("code") or "").strip()
                    name = (row.get("name") or "").strip()
                    kind = (row.get("place_type") or "").strip().lower()
                    parent_code = (row.get("parent_code") or "").strip()
                    if not code or not name:
                        raise CommandError(f"Row {line}: code and name are required.")
                    parent = None
                    if parent_code:
                        try:
                            parent = GeographicPlace.objects.get(code=parent_code)
                        except GeographicPlace.DoesNotExist as exc:
                            raise CommandError(
                                f"Row {line}: parent {parent_code!r} must be imported first."
                            ) from exc
                    place = GeographicPlace.objects.filter(code=code).first()
                    if place is None:
                        place = GeographicPlace(code=code)
                    place.name = name
                    place.place_type = kind
                    place.parent = parent
                    place.data_source = source
                    try:
                        place.full_clean()
                    except ValidationError as exc:
                        raise CommandError(f"Row {line}: {exc}") from exc
                    place.save()
                    count += 1
        except OSError as exc:
            raise CommandError(f"Could not read geographic CSV: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(f"Imported {count} geographic places."))
