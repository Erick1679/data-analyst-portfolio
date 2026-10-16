"""Preview or apply small, explicitly selected country batches safely.

The default is read-only. --apply reruns preflight then saves an entire
batch inside one transaction; a failure rolls back the whole batch.
Only independently reviewed geographic reference data should be used.
"""
import re

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from analytics.models import DataSource, GeographicPlace


class Command(BaseCommand):
    help = "Preview country subdivision batches; use --apply to save atomically."

    def add_arguments(self, parser):
        parser.add_argument(
            "--countries", nargs="+", required=True,
            help="Two-letter ISO codes separated by spaces, e.g. TZ RW.",
        )
        parser.add_argument("--source-id", type=int, required=True)
        parser.add_argument(
            "--include-nested", action="store_true",
            help="Include nested subdivisions only if their parents resolve.",
        )
        parser.add_argument(
            "--apply", action="store_true",
            help="After a complete preflight, apply the whole batch atomically.",
        )

    def handle(self, *args, **options):
        countries = [code.strip().upper() for code in options["countries"]]
        if not 1 <= len(countries) <= 5:
            raise CommandError("Choose 1–5 countries per batch for review.")
        if (any(not re.fullmatch(r"[A-Z]{2}", code) for code in countries)
                or len(set(countries)) != len(countries)):
            raise CommandError("Use unique ISO alpha-2 country codes only.")

        try:
            source = DataSource.objects.get(pk=options["source_id"])
        except DataSource.DoesNotExist as exc:
            raise CommandError("The specified data source does not exist.") from exc
        if not source.publisher.strip() or not source.licence_notes.strip():
            raise CommandError("Record publisher and licensing notes before importing.")

        registered = set(
            GeographicPlace.objects.filter(
                code__in=countries, place_type=GeographicPlace.COUNTRY
            ).values_list("code", flat=True)
        )
        missing = sorted(set(countries) - registered)
        if missing:
            raise CommandError(
                "Country roots missing: " + ", ".join(missing) +
                ". Import countries before subdivisions."
            )

        self.stdout.write(
            "Batch preflight (read-only): " + ", ".join(countries)
        )
        for code in countries:
            call_command(
                "import_iso_subdivisions",
                country=code, source_id=source.pk, dry_run=True,
                include_nested=options["include_nested"], stdout=self.stdout,
            )

        if not options["apply"]:
            self.stdout.write(self.style.SUCCESS(
                "Preview complete: nothing was saved. "
                "Review skipped records and source rights before using --apply."
            ))
            return

        self.stdout.write("Preflight complete. Starting atomic batch import.")
        try:
            with transaction.atomic():
                for code in countries:
                    call_command(
                        "import_iso_subdivisions",
                        country=code, source_id=source.pk, dry_run=False,
                        include_nested=options["include_nested"], stdout=self.stdout,
                    )
        except Exception as exc:
            # Rollback is guaranteed by the outer transaction, including
            # any earlier successfully imported countries in this batch.
            raise CommandError(
                f"Batch failed and all batch writes were rolled back: {exc}"
            ) from exc

        self.stdout.write(self.style.SUCCESS(
            "Batch completed. Existing records and data source approval "
            "flags were not modified."
        ))
