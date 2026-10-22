"""Security tests for restricted dataset grant issuance."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from auditlog.models import AuditEvent
from organizations.models import Organization, OrganizationMembership

from .models import CorporateDataset, DatasetAccessGrant
from .services import issue_dataset_access_grant


class DatasetGrantIssuanceTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            username="grant_issuer_owner",
            password="local-test-password",
        )
        self.recipient = User.objects.create_user(
            username="grant_issuer_recipient",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Grant Issuance Company",
            slug="grant-issuance-company",
        )

        self.owner_membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role="owner",
        )

        self.recipient_membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.recipient,
            role="analyst",
        )

        self.dataset = CorporateDataset.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name="Restricted Issuance Dataset",
            classification="restricted",
        )

    def issue(self, **overrides):
        arguments = {
            "user": self.owner,
            "organization": self.organization,
            "dataset": self.dataset,
            "membership": self.recipient_membership,
        }
        arguments.update(overrides)
        return issue_dataset_access_grant(**arguments)

    def test_owner_issues_grant_with_audit_event(self):
        grant = self.issue()

        self.assertTrue(grant.is_active)
        self.assertEqual(grant.membership, self.recipient_membership)
        self.assertEqual(grant.dataset, self.dataset)
        self.assertEqual(grant.granted_by, self.owner)
        self.assertEqual(DatasetAccessGrant.objects.count(), 1)

        event = AuditEvent.objects.get()
        self.assertEqual(event.action, "dataset.grant_created")
        self.assertEqual(event.outcome, "success")
        self.assertEqual(event.organization, self.organization)
        self.assertEqual(event.actor, self.owner)
        self.assertEqual(event.target_id, str(grant.id))

    def test_administrator_can_issue_grant(self):
        self.owner_membership.role = "admin"
        self.owner_membership.save(update_fields=["role"])

        grant = self.issue()
        self.assertTrue(grant.is_active)

    def test_unauthorized_role_cannot_issue_grant(self):
        self.owner_membership.role = "analyst"
        self.owner_membership.save(update_fields=["role"])

        with self.assertRaises(PermissionDenied):
            self.issue()

        self.assertEqual(DatasetAccessGrant.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_cross_organization_dataset_is_rejected(self):
        other = Organization.objects.create(
            name="Outside Dataset Company",
            slug="outside-dataset-company",
        )
        outside_dataset = CorporateDataset.objects.create(
            organization=other,
            created_by=self.owner,
            name="Outside Restricted Dataset",
            classification="restricted",
        )

        with self.assertRaises(PermissionDenied):
            self.issue(dataset=outside_dataset)

        self.assertEqual(DatasetAccessGrant.objects.count(), 0)

    def test_cross_organization_membership_is_rejected(self):
        other = Organization.objects.create(
            name="Outside Membership Company",
            slug="outside-membership-company",
        )
        other_membership = OrganizationMembership.objects.create(
            organization=other,
            user=self.recipient,
            role="viewer",
        )

        with self.assertRaises(PermissionDenied):
            self.issue(membership=other_membership)

        self.assertEqual(DatasetAccessGrant.objects.count(), 0)

    def test_inactive_recipient_is_rejected(self):
        self.recipient_membership.is_active = False
        self.recipient_membership.save(update_fields=["is_active"])

        with self.assertRaises(PermissionDenied):
            self.issue()

        self.assertEqual(DatasetAccessGrant.objects.count(), 0)

    def test_duplicate_active_grant_is_rejected(self):
        self.issue()

        with self.assertRaises(ValidationError):
            self.issue()

        self.assertEqual(DatasetAccessGrant.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_revoked_grant_can_be_reactivated(self):
        grant = self.issue()

        grant.is_active = False
        grant.revoked_at = timezone.now()
        grant.save(update_fields=["is_active", "revoked_at"])

        restored = self.issue()

        self.assertEqual(restored.pk, grant.pk)
        self.assertTrue(restored.is_active)
        self.assertIsNone(restored.revoked_at)
        self.assertEqual(DatasetAccessGrant.objects.count(), 1)
        self.assertEqual(
            AuditEvent.objects.filter(
                action="dataset.grant_reactivated"
            ).count(),
            1,
        )

    def test_audit_failure_rolls_back_grant(self):
        with patch(
            "datasets.services.record_audit_event",
            side_effect=RuntimeError("Simulated audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.issue()

        self.assertEqual(DatasetAccessGrant.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)
