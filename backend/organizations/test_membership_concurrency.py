"""Concurrency tests for corporate ownership safeguards."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TransactionTestCase

from auditlog.models import AuditEvent

from .models import Organization, OrganizationMembership
from .services import (
    change_organization_membership_role,
    deactivate_organization_membership,
)


class MembershipOwnershipConcurrencyTests(TransactionTestCase):

    def setUp(self):
        User = get_user_model()

        self.first_user = User.objects.create_user(
            username="concurrent_membership_owner_one",
            password="local-test-password",
        )
        self.second_user = User.objects.create_user(
            username="concurrent_membership_owner_two",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Concurrent Ownership Company",
            slug="concurrent-ownership-company",
        )

        self.first_membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.first_user,
            role="owner",
        )
        self.second_membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.second_user,
            role="owner",
        )

    def run_simultaneous_operation(self, operation):
        barrier = Barrier(2, timeout=10)

        def attempt(user, membership):
            close_old_connections()

            try:
                barrier.wait()

                result = operation(
                    actor=user,
                    organization=self.organization,
                    membership_id=membership.pk,
                )
                return ("success", str(result.pk))

            except Exception as error:
                return (
                    "error",
                    f"{type(error).__name__}: {error}",
                )

            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    attempt,
                    self.first_user,
                    self.first_membership,
                ),
                executor.submit(
                    attempt,
                    self.second_user,
                    self.second_membership,
                ),
            ]

            results = [
                future.result(timeout=20)
                for future in futures
            ]

        return results

    def assert_ownership_preserved(self, results):
        active_owner_count = OrganizationMembership.objects.filter(
            organization=self.organization,
            role="owner",
            is_active=True,
            user__is_active=True,
        ).count()

        success_count = sum(
            status == "success"
            for status, _ in results
        )

        audit_count = AuditEvent.objects.filter(
            organization=self.organization,
            action="membership.changed",
            outcome="success",
        ).count()

        self.assertGreaterEqual(active_owner_count, 1)
        self.assertLessEqual(success_count, 1)
        self.assertEqual(audit_count, success_count)

    def test_simultaneous_owner_deactivations_preserve_owner(self):
        results = self.run_simultaneous_operation(
            deactivate_organization_membership
        )

        print("\nConcurrent owner deactivation results:", results)
        self.assert_ownership_preserved(results)

    def test_simultaneous_owner_demotions_preserve_owner(self):
        def demote(**kwargs):
            return change_organization_membership_role(
                role="admin",
                **kwargs,
            )

        results = self.run_simultaneous_operation(demote)

        print("\nConcurrent owner demotion results:", results)
        self.assert_ownership_preserved(results)
