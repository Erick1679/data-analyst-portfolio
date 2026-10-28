"""Preview or prune expired authentication audit events."""

import calendar
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from auditlog.models import AuthenticationEvent


def retention_cutoffs(now):
    """Return the exact retention boundaries.

    Failed logins: 90 elapsed days.
    Successful logins and logouts: 12 calendar months.
    Leap-day dates clamp to the final valid February day.
    """
    year = now.year - 1
    day = min(
        now.day,
        calendar.monthrange(year, now.month)[1],
    )
    annual = now.replace(year=year, day=day)

    return {
        AuthenticationEvent.LOGIN_SUCCESS: annual,
        AuthenticationEvent.LOGIN_FAILURE: (
            now - timedelta(days=90)
        ),
        AuthenticationEvent.LOGOUT: annual,
    }


class Command(BaseCommand):
    help = (
        "Preview expired authentication events, or delete them "
        "only when --apply is explicitly supplied."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Delete expired records instead of previewing.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        cutoffs = retention_cutoffs(now)

        # Only known authentication event types are eligible.
        # Strictly older: records at the cutoff are retained.
        eligible = {
            event_type: AuthenticationEvent.objects.filter(
                event_type=event_type,
                created_at__lt=cutoff,
            )
            for event_type, cutoff in cutoffs.items()
        }

        counts = {
            event_type: queryset.count()
            for event_type, queryset in eligible.items()
        }

        for event_type, cutoff in cutoffs.items():
            self.stdout.write(
                f"{event_type}: eligible={counts[event_type]} "
                f"cutoff={cutoff.isoformat()}"
            )

        total = sum(counts.values())

        if not options["apply"]:
            self.stdout.write(
                f"PREVIEW ONLY: {total} eligible records. "
                "No records deleted."
            )
            return

        # All three deletion groups must complete together.
        with transaction.atomic():
            for queryset in eligible.values():
                queryset.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"APPLIED: expired authentication events "
                f"deleted; preview count was {total}."
            )
        )
