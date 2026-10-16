"""Deprecated Kenya-specific command; use the geographic importers instead."""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Deprecated: use import_geographic_indicators instead."

    def handle(self, *args, **options):
        raise CommandError(
            "This command was retired when the platform became worldwide. "
            "Use import_geographic_indicators with place_code instead."
        )
