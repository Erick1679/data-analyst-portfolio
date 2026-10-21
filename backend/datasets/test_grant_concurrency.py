"""Concurrency tests for restricted dataset grant operations."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TransactionTestCase

from auditlog.models import AuditEvent
from organizations.models import Organization, OrganizationMembership

from .models import CorporateDataset, DatasetAccessGrant
from .services import (
    issue_dataset_access_grant,
    revoke_dataset_access_grant,
)


class GrantConcurrencyTests(TransactionTestCase):

    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            username="concurrent_grant_owner",
            password="local-test-password",
        )

        self.recipient = User.objects.create_user(
            username="concurrent_grant_recipient",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Concurrent Grant Company",
            slug="concurrent-grant-company",
        )

        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role="owner",
        )

        self.membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.recipient,
            role="analyst",
        )

        self.dataset = CorporateDataset.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name="Concurrent Restricted Dataset",
            classification="restricted",
        )

    def test_simultaneous_issuance_never_creates_duplicate_grants(self):
        barrier = Barrier(2, timeout=10)

        def attempt_issue():
            close_old_connections()

            try:
                barrier.wait()

                grant = issue_dataset_access_grant(
                    user=self.owner,
                    organization=self.organization,
                    dataset=self.dataset,
                    membership=self.membership,
                )

                return ("success", str(grant.id))

            except Exception as error:
                return ("error", f"{type(error).__name__}: {error}")

            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(attempt_issue)
                for _ in range(2)
            ]

            results = [
                future.result(timeout=20)
                for future in futures
            ]

        print("\nConcurrent issuance results:", results)

        self.assertEqual(
            DatasetAccessGrant.objects.filter(
                dataset=self.dataset,
                membership=self.membership,
            ).count(),
            1,
        )

        self.assertEqual(
            AuditEvent.objects.filter(
                action="dataset.grant_created",
            ).count(),
            1,
        )

        self.assertEqual(
            sum(status == "success" for status, _ in results),
            1,
        )

    def test_simultaneous_revocation_preserves_audit_integrity(self):
        grant = issue_dataset_access_grant(
            user=self.owner,
            organization=self.organization,
            dataset=self.dataset,
            membership=self.membership,
        )

        barrier = Barrier(2, timeout=10)

        def attempt_revoke():
            close_old_connections()

            try:
                barrier.wait()

                revoked = revoke_dataset_access_grant(
                    user=self.owner,
                    organization=self.organization,
                    grant_id=grant.id,
                )

                return ("success", str(revoked.id))

            except Exception as error:
                return (
                    "error",
                    f"{type(error).__name__}: {error}",
                )

            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(attempt_revoke)
                for _ in range(2)
            ]

            results = [
                future.result(timeout=20)
                for future in futures
            ]

        print("\nConcurrent revocation results:", results)

        grant.refresh_from_db()

        self.assertFalse(grant.is_active)
        self.assertIsNotNone(grant.revoked_at)

        self.assertEqual(
            AuditEvent.objects.filter(
                action="dataset.grant_revoked",
                target_id=str(grant.id),
            ).count(),
            1,
        )

        self.assertEqual(
            sum(status == "success" for status, _ in results),
            1,
        )
