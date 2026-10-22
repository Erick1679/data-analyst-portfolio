"""Safely import ISO 3166-2 subdivisions for one country at a time.

Use --include-nested for deeper hierarchies (e.g. Uganda's regions/districts).
No scraping, updates to existing places or approval-flag changes are performed.
ISO subdivisions may be incomplete or use different local administrative codes.
"""
import re
import unicodedata
from collections import Counter

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from analytics.models import DataSource, GeographicPlace


TYPE_MAP = {
    "State": "state",
    "Province": "province",
    "Region": "region",
    "Geographical region": "region",
    "Administrative region": "region",
    "County": "county",
    "District": "district",
    "Federal district": "district",
    "Capital district": "district",
    "City": "city",
    "Town": "town",
    "Municipality": "municipality",
    "Department": "department",
    "Prefecture": "prefecture",
    "Territory": "territory",
    "Outlying area": "territory",
}


def comparison_name(name):
    """Compare likely alternate administrative names without changing them."""
    simplified = unicodedata.normalize("NFKD", name.casefold())
    simplified = "".join(c for c in simplified if not unicodedata.combining(c))
    simplified = re.sub(r"[^a-z0-9 ]", " ", simplified)
    parts = simplified.split()
    if len(parts) > 1 and parts[-1] in {"county", "city"}:
        parts.pop()
    return " ".join(parts)


class Command(BaseCommand):
    help = "Preview/import one country's ISO subdivisions, optionally including nested levels."

    def add_arguments(self, parser):
        parser.add_argument("--country", required=True, help="ISO alpha-2 code, e.g. UG")
        parser.add_argument("--source-id", required=True, type=int)
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Preview without changing the database (strongly recommended).",
        )
        parser.add_argument(
            "--include-nested", action="store_true",
            help="Include supported nested subdivisions only when parents can be resolved.",
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

        records = {
            record.code: record
            for record in pycountry.subdivisions if record.country_code == code
        }
        if not records:
            self.stdout.write(f"No ISO subdivisions found for {code}. No changes made.")
            return

        # Fetch pre-existing codes globally to avoid a cross-country code collision.
        existing_by_code = {
            place.code: place for place in
            GeographicPlace.objects.filter(code__in=records).select_related("parent")
        }
        existing_by_code[code] = country

        # Index existing descendants for parent-aware alias detection.
        # This also handles previously imported counties with non-ISO local codes.
        by_parent_name_type = {}
        level = [country.pk]
        while level:
            children = list(
                GeographicPlace.objects.filter(parent_id__in=level)
                .select_related("parent")
            )
            level = [place.pk for place in children]
            for place in children:
                existing_by_code[place.code] = place
                by_parent_name_type[(
                    place.parent.code, place.place_type,
                    comparison_name(place.name),
                )] = place

        pending = {}
        unsupported = Counter()
        nested_deferred = 0
        for record in records.values():
            kind = TYPE_MAP.get(record.type)
            if not kind:
                unsupported[record.type] += 1
                continue
            if getattr(record, "parent_code", None) and not options["include_nested"]:
                nested_deferred += 1
                continue
            pending[record.code] = (record, kind)

        # 'resolved' maps an ISO code to an existing or proposed stored place code.
        # No objects are created during the entire planning/dry-run phase.
        resolved = {code: code}
        planned = []  # (code, name, kind, resolved parent code)
        aliases = []
        retained = 0

        while pending:
            progressed = False
            for record_code in sorted(tuple(pending)):
                record, kind = pending[record_code]
                source_parent = getattr(record, "parent_code", None) or code
                if source_parent not in resolved:
                    continue
                parent_code = resolved[source_parent]

                match = existing_by_code.get(record_code)
                if match is not None:
                    if (match.parent is None or match.parent.code != parent_code
                            or match.place_type != kind):
                        raise CommandError(
                            f"Code conflict: {record_code} exists as "
                            f"{match.label_path} ({match.place_type}); "
                            "no changes made."
                        )
                    retained += 1
                    resolved[record_code] = match.code
                else:
                    key = (parent_code, kind, comparison_name(record.name))
                    similar = by_parent_name_type.get(key)
                    if similar is not None:
                        aliases.append((
                            record.code, similar.code, record.name, similar.name,
                        ))
                        resolved[record_code] = similar.code
                    else:
                        planned.append((record.code, record.name, kind, parent_code))
                        resolved[record_code] = record.code
                        # The placeholder is only used for matching; it is not saved.
                        by_parent_name_type[key] = GeographicPlace(
                            code=record.code, name=record.name, place_type=kind
                        )
                del pending[record_code]
                progressed = True
            if not progressed:
                break

        # A pending record may depend on an unsupported or missing ISO parent.
        # Defer it rather than guessing an incorrect geographic relationship.
        unresolved = sorted(pending)

        if not options["dry_run"]:
            for place_code, name, kind, parent_code in planned:
                try:
                    parent = GeographicPlace.objects.get(code=parent_code)
                except GeographicPlace.DoesNotExist as exc:
                    raise CommandError(
                        f"Missing resolved parent {parent_code} for {place_code}."
                    ) from exc
                place = GeographicPlace(
                    code=place_code, name=name, place_type=kind,
                    parent=parent, data_source=source,
                )
                try:
                    place.full_clean()
                except ValidationError as exc:
                    raise CommandError(
                        f"Invalid subdivision {place_code}: {exc}. "
                        "The transaction will be rolled back."
                    ) from exc
                place.save()

        self.stdout.write(
            ("Dry run" if options["dry_run"] else "Import complete") +
            f" for {country.name} ({code}): {len(planned)} new subdivisions; "
            f"{retained} existing codes retained; {len(aliases)} possible "
            f"duplicates/aliases skipped; {sum(unsupported.values())} "
            f"unsupported types deferred; {nested_deferred} nested subdivisions "
            f"not requested; {len(unresolved)} unresolved-parent records deferred."
        )
        for external, local, external_name, local_name in aliases[:15]:
            self.stdout.write(
                f"  Possible equivalent: {external} ({external_name}) "
                f"-> retained {local} ({local_name})"
            )
        if len(aliases) > 15:
            self.stdout.write(f"  ... and {len(aliases) - 15} other possible aliases.")
        for name, count in unsupported.most_common(10):
            self.stdout.write(f"  Deferred type: {name} ({count})")
        if unresolved:
            self.stdout.write(
                "  Unresolved parent examples: " + ", ".join(unresolved[:10])
            )
        self.stdout.write(
            "Existing records, source ownership and publication/commercial "
            "approval flags have not been modified."
        )
