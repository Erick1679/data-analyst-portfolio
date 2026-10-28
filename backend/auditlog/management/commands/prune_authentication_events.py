"""Preview or prune expired authentication audit events."""

import calendar
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from auditlog.models import AuthenticationEvent


# Fixed PostgreSQL advisory lock namespace for this cleanup.
# The same lock is shared by every process using this command
# against the same PostgreSQL database.
LOCK_NAMESPACE = 162774201
LOCK_OPERATION = 771201


def retention_cutoffs(now):
    """Return strict retention boundaries."""
    previous_year = now.year - 1
    day = min(
        now.day,
        calendar.monthrange(previous_year, now.month)[1],
    )
    annual = now.replace(year=previous_year, day=day)

    return {
        AuthenticationEvent.LOGIN_SUCCESS: annual,
        AuthenticationEvent.LOGIN_FAILURE: now - timedelta(days=90),
        AuthenticationEvent.LOGOUT: annual,
    }


class Command(BaseCommand):
    help = (
        "Preview authentication event retention, or delete "
        "only with --apply and verified PostgreSQL identity."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Perform deletion after database identity verification.",
        )
        parser.add_argument(
            "--expected-database",
            default=None,
            help="Exact PostgreSQL database name required with --apply.",
        )
        parser.add_argument(
            "--expected-user",
            default=None,
            help="Exact PostgreSQL current_user required with --apply.",
        )

    def _verify_target_and_lock(self, expected_database, expected_user):
        """Verify live database identity and acquire exclusive job lock.

        Must be called inside transaction.atomic(), so the
        transaction-scoped advisory lock survives through deletion.
        """
        if connection.vendor != "postgresql":
            raise CommandError(
                "Deletion requires a PostgreSQL database."
            )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT current_database(), current_user"
            )
            actual_database, actual_user = cursor.fetchone()

            if (
                actual_database != expected_database
                or actual_user != expected_user
            ):
                raise CommandError(
                    "Live PostgreSQL identity does not match "
                    "the explicitly expected database and user."
                )

            cursor.execute(
                "SELECT pg_try_advisory_xact_lock(%s, %s)",
                [LOCK_NAMESPACE, LOCK_OPERATION],
            )
            locked = cursor.fetchone()[0]

        if not locked:
            raise CommandError(
                "Another authentication retention cleanup "
                "holds the PostgreSQL advisory lock."
            )

    def _eligible(self, cutoffs):
        return {
            event_type: AuthenticationEvent.objects.filter(
                event_type=event_type,
                created_at__lt=cutoff,
            )
            for event_type, cutoff in cutoffs.items()
        }

    def _report_counts(self, cutoffs, counts):
        for event_type, cutoff in cutoffs.items():
            self.stdout.write(
                f"{event_type}: eligible={counts[event_type]} "
                f"cutoff={cutoff.isoformat()}"
            )

    def handle(self, *args, **options):
        apply = options["apply"]
        expected_database = options["expected_database"]
        expected_user = options["expected_user"]

        if apply and (
            not expected_database
            or not expected_database.strip()
            or not expected_user
            or not expected_user.strip()
        ):
            raise CommandError(
                "--apply requires both --expected-database "
                "and --expected-user."
            )

        if not apply:
            now = timezone.now()
            cutoffs = retention_cutoffs(now)
            eligible = self._eligible(cutoffs)

            counts = {
                event_type: queryset.count()
                for event_type, queryset in eligible.items()
            }
            self._report_counts(cutoffs, counts)

            self.stdout.write(
                f"PREVIEW ONLY: {sum(counts.values())} "
                "eligible records. No records deleted."
            )
            return

        # Identity verification, lock acquisition, count and
        # deletion happen within the same transaction.
        with transaction.atomic():
            self._verify_target_and_lock(
                expected_database,
                expected_user,
            )

            now = timezone.now()
            cutoffs = retention_cutoffs(now)
            eligible = self._eligible(cutoffs)

            counts = {
                event_type: queryset.count()
                for event_type, queryset in eligible.items()
            }
            self._report_counts(cutoffs, counts)

            deleted_counts = {}

            for event_type, queryset in eligible.items():
                _, by_model = queryset.delete()

                # Django reports deletions by model label.
                # Count only actual AuthenticationEvent rows,
                # excluding any hypothetical related-model rows.
                deleted_counts[event_type] = by_model.get(
                    AuthenticationEvent._meta.label,
                    0,
                )

        # Report success only after transaction.atomic()
        # has exited and PostgreSQL has committed.
        self.stdout.write(
            self.style.SUCCESS(
                "APPLIED: authentication retention cleanup "
                "committed successfully. "
                f"deleted_total={sum(deleted_counts.values())}"
            )
        )

        for event_type, deleted in deleted_counts.items():
            self.stdout.write(
                f"{event_type}: deleted={deleted}"
            )
