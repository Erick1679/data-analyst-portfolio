"""Conservatively import *top-level* ISO 3166-2 subdivisions, country by country.

ISO 3166-2 is not a worldwide city directory. Parent-coded (nested)
subdivisions and unrecognised administrative types are deferred for review.
Existing records are never overwritten, and manual/ISO aliases are reported.
"""
import re
import unicodedata
from collections import Counter

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from analytics.models import DataSource, GeographicPlace


# Add new types only when their semantics have been reviewed.
TYPE_MAP = {
    "State": "state",
    "Province": "province",
    "Region": "region",
    "Administrative region": "region",
    "County": "county",
    "District": "district",
    "Federal district": "district",
    "Capital district": "district",
    "City": "city",
    "Municipality": "municipality",
    "Department": "department",
    "Prefecture": "prefecture",
    "Territory": "territory",
    "Outlying area": "territory",
}


def comparison_name(name):
    """Flag likely alternate spellings of the same administrative area."""
    simplified = unicodedata.normalize("NFKD", name.casefold())
    simplified = "".join(c for c in simplified if not unicodedata.combining(c))
    simplified = re.sub(r"[^a-z0-9 ]", " ", simplified)
    parts = simplified.split()
    if len(parts) > 1 and parts[-1] in {"county", "city"}:
        parts.pop()
    return " ".join(parts)


class Command(BaseCommand):
    help = "Preview/import top-level ISO subdivisions for one country at a time."

    def add_arguments(self, parser):
        parser.add_argument("--country", required=True, help="ISO alpha-2 code (e.g. KE)")
        parser.add_argument("--source-id", required=True, type=int)
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Preview without changing the database (recommended first).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            import pycountry
        except ImportError as exc:
            raise CommandError("Install the pycountry dependency first.") from exc

        code = options["country"].upper().strip()
        if not re.fullmatch(r"[A-Z]{2}", code):
            raise CommandError("--country must be a two-letter ISO country code.")

        try:
            country = GeographicPlace.objects.get(code=code, place_type="country")
        except GeographicPlace.DoesNotExist as exc:
            raise CommandError(f"Country {code} is missing; import countries first.") from exc

        try:
            source = DataSource.objects.get(pk=options["source_id"])
        except DataSource.DoesNotExist as exc:
            raise CommandError("The specified geographic DataSource does not exist.") from exc
        if not source.publisher.strip() or not source.licence_notes.strip():
            raise CommandError("The data source needs publisher and licence notes.")

        existing = GeographicPlace.objects.filter(parent=country)
        existing_by_code = {place.code: place for place in existing}
        by_name_and_type = {
            (comparison_name(place.name), place.place_type): place
            for place in existing
        }

        top_level = []
        nested = 0
        for record in pycountry.subdivisions:
            if record.country_code != code:
                continue
            if getattr(record, "parent_code", None):
                nested += 1
            else:
                top_level.append(record)

        new = []
        retained = 0
        aliases = []
        unsupported = Counter()
        for record in sorted(top_level, key=lambda x: x.code):
            kind = TYPE_MAP.get(record.type)
            if not kind:
                unsupported[record.type] += 1
                continue

            match = GeographicPlace.objects.filter(code=record.code).first()
            if match:
                if match.parent_id != country.pk or match.place_type != kind:
                    raise CommandError(
                        f"Code conflict: {record.code} already belongs to "
                        f"{match.label_path} ({match.place_type}). No changes made."
                    )
                retained += 1
                continue

            similar = by_name_and_type.get((comparison_name(record.name), kind))
            if similar:
                aliases.append((record.code, similar.code, record.name, similar.name))
                continue

            place = GeographicPlace(
                code=record.code, name=record.name, place_type=kind,
                parent=country, data_source=source,
            )
            try:
                place.full_clean()
            except ValidationError as exc:
                raise CommandError(
                    f"Invalid subdivision {record.code}: {exc}. No changes made."
                ) from exc
            new.append(place)
            by_name_and_type[(comparison_name(record.name), kind)] = place

        if not options["dry_run"]:
            for place in new:
                place.save()

        self.stdout.write(
            ("Dry run" if options["dry_run"] else "Import complete") +
            f" for {country.name} ({code}): {len(new)} new top-level subdivisions; "
            f"{retained} existing codes retained; {len(aliases)} possible "
            f"duplicates/aliases skipped; {sum(unsupported.values())} unsupported "
            f"types deferred; {nested} nested subdivisions deferred."
        )
        for external, local, external_name, local_name in aliases[:15]:
            self.stdout.write(
                f"  Possible equivalent: {external} ({external_name}) "
                f"-> retained {local} ({local_name})"
            )
        if len(aliases) > 15:
            self.stdout.write(f"  ... and {len(aliases) - 15} other possible aliases.")
        for type_name, count in unsupported.most_common(10):
            self.stdout.write(f"  Deferred type: {type_name} ({count})")
        self.stdout.write(
            "Existing records, source ownership and publication/commercial "
            "approval flags have not been modified."
        )
