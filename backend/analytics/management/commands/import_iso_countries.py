"""Import ISO 3166-1 country/territory codes from the open-source pycountry package.

This command never downloads data, overwrites existing records, approves
publication or approves commercial reuse. Place statistics require separate
permissioned sources and importing.
"""
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from analytics.models import DataSource, GeographicPlace


class Command(BaseCommand):
    help = "Import ISO 3166-1 countries using an explicitly recorded data source."

    def add_arguments(self, parser):
        parser.add_argument("--source-id", type=int, required=True)
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Preview new and existing countries without changing the database.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            import pycountry
        except ImportError as exc:
            raise CommandError(
                "Missing pycountry. Install backend/requirements.txt first."
            ) from exc
        try:
            source = DataSource.objects.get(pk=options["source_id"])
        except DataSource.DoesNotExist as exc:
            raise CommandError("Create a DataSource and supply its ID.") from exc
        if not source.publisher.strip() or not source.licence_notes.strip():
            raise CommandError("Record the publisher and licence before importing.")

        added = 0
        retained = 0
        for item in sorted(pycountry.countries, key=lambda c: c.alpha_2):
            code = item.alpha_2
            current = GeographicPlace.objects.filter(code=code).first()
            if current is not None:
                if current.place_type != GeographicPlace.COUNTRY or current.parent_id:
                    raise CommandError(
                        f"{code} is in use by a non-country or child record; "
                        "resolve the conflict before importing."
                    )
                retained += 1
                continue
            if not options["dry_run"]:
                place = GeographicPlace(
                    code=code, name=item.name, place_type=GeographicPlace.COUNTRY,
                    data_source=source,
                )
                try:
                    place.full_clean()
                except ValidationError as exc:
                    raise CommandError(
                        f"Invalid reference record for {code}: {exc}"
                    ) from exc
                place.save()
            added += 1

        mode = "Dry run" if options["dry_run"] else "Import complete"
        self.stdout.write(self.style.SUCCESS(
            f"{mode}: {added} new countries/territories; "
            f"{retained} existing country records retained. "
            "No publishing permissions have been changed."
        ))
