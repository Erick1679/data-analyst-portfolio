"""Preview local authority CSV records; import only with explicit --apply.

Local authorities are institutions and are never added to GeographicPlace.
CSV columns: name,authority_type,import_decision,notes.
Use import_decision=hold for naming disputes. Existing records are untouched.
"""
import csv
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from analytics.models import DataSource, GeographicPlace, LocalAuthority


FIELDS = ("name", "authority_type", "import_decision", "notes")


class Command(BaseCommand):
    help = (
        "Preview authority records from a reviewed CSV. "
        "Use --apply only after checking the report and source rights."
    )

    def add_arguments(self, parser):
        parser.add_argument("file", type=Path)
        parser.add_argument("--country", type=str, required=True)
        parser.add_argument("--source-id", type=int, required=True)
        parser.add_argument(
            "--apply", action="store_true",
            help="Save new records in one transaction after full validation.",
        )

    def handle(self, *args, **options):
        country_code = options["country"].strip().upper()
        try:
            country = GeographicPlace.objects.get(
                code=country_code, place_type=GeographicPlace.COUNTRY
            )
        except GeographicPlace.DoesNotExist as exc:
            raise CommandError(
                f"Country root {country_code!r} does not exist."
            ) from exc

        try:
            source = DataSource.objects.get(pk=options["source_id"])
        except DataSource.DoesNotExist as exc:
            raise CommandError("The specified DataSource does not exist.") from exc
        if not source.publisher.strip() or not source.licence_notes.strip():
            raise CommandError(
                "Record the publisher and licence review notes first."
            )

        valid_types = {value for value, _ in LocalAuthority.AUTHORITY_TYPES}
        names_seen = set()
        new_records = []
        existing_count = 0
        held_count = 0
        try:
            with options["file"].open(
                newline="", encoding="utf-8-sig"
            ) as handle:
                reader = csv.DictReader(handle)
                if reader.fieldnames != list(FIELDS):
                    raise CommandError(
                        "Expected CSV columns: " + ",".join(FIELDS)
                    )
                for line_number, row in enumerate(reader, start=2):
                    if None in row:
                        raise CommandError(
                            f"Row {line_number}: unexpected extra CSV columns."
                        )
                    name = (row["name"] or "").strip()
                    kind = (row["authority_type"] or "").strip().lower()
                    decision = (row["import_decision"] or "").strip().lower()
                    notes = (row["notes"] or "").strip()
                    if not name or kind not in valid_types:
                        raise CommandError(
                            f"Row {line_number}: valid name and authority_type required."
                        )
                    if decision not in {"include", "hold"}:
                        raise CommandError(
                            f"Row {line_number}: import_decision must be include or hold."
                        )
                    if name.casefold() in names_seen:
                        raise CommandError(
                            f"Row {line_number}: duplicated council name {name!r}."
                        )
                    names_seen.add(name.casefold())
                    if decision == "hold":
                        if not notes:
                            raise CommandError(
                                f"Row {line_number}: explain why the council is on hold."
                            )
                        held_count += 1
                        self.stdout.write(f"HOLD: {name} — {notes}")
                        continue

                    existing = LocalAuthority.objects.filter(
                        country=country, name__iexact=name
                    ).first()
                    if existing:
                        if existing.authority_type != kind or existing.source_id != source.pk:
                            raise CommandError(
                                f"Row {line_number}: existing council {name!r} "
                                "has a different authority type or DataSource. "
                                "Resolve the conflict manually; no records imported."
                            )
                        existing_count += 1
                        self.stdout.write(f"EXISTING (unchanged): {name}")
                        continue

                    record = LocalAuthority(
                        name=name, country=country,
                        authority_type=kind, source=source,
                        verification_status="pending",
                        jurisdiction=None, notes=notes,
                    )
                    try:
                        record.full_clean()
                    except ValidationError as exc:
                        raise CommandError(
                            f"Row {line_number}: {exc}"
                        ) from exc
                    new_records.append(record)
                    self.stdout.write(f"NEW (pending): {name}")
        except (OSError, UnicodeError, csv.Error) as exc:
            raise CommandError(f"Could not read council CSV: {exc}") from exc

        self.stdout.write(
            f"Preflight: {len(new_records)} new, "
            f"{existing_count} existing, {held_count} held. "
            "No geographic places or source approvals will be modified."
        )
        if not options["apply"]:
            self.stdout.write(self.style.SUCCESS(
                "PREVIEW ONLY: no records saved. "
                "Review the list before rerunning with --apply."
            ))
            return

        try:
            with transaction.atomic():
                for record in new_records:
                    record.full_clean()
                    record.save()
        except (ValidationError, Exception) as exc:
            raise CommandError(
                f"Import failed; changes rolled back: {exc}"
            ) from exc
        self.stdout.write(self.style.SUCCESS(
            f"Imported {len(new_records)} new local authorities. "
            f"Skipped {existing_count} existing and {held_count} held. "
            "All new records are pending verification, with no jurisdiction."
        ))
