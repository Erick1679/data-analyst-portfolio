"""Security tests for restricted dataset grant revocation."""

import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.test import TestCase

from auditlog.models import AuditEvent
from organizations.models import Organization, OrganizationMembership

from .models import CorporateDataset, DatasetAccessGrant
from .services import (
    issue_dataset_access_grant,
    revoke_dataset_access_grant,
)


class DatasetGrantRevocationTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            username="grant_revocation_owner",
            password="local-test-password",
        )
        self.recipient = User.objects.create_user(
            username="grant_revocation_recipient",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Grant Revocation Company",
            slug="grant-revocation-company",
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
            name="Restricted Revocation Dataset",
            classification="restricted",
        )

        self.grant = issue_dataset_access_grant(
            user=self.owner,
            organization=self.organization,
            dataset=self.dataset,
            membership=self.recipient_membership,
        )

    def revoke(self, **overrides):
        arguments = {
            "user": self.owner,
            "organization": self.organization,
            "grant_id": self.grant.id,
        }
        arguments.update(overrides)
        return revoke_dataset_access_grant(**arguments)

    def test_owner_revokes_grant_with_audit(self):
        revoked = self.revoke()

        self.assertFalse(revoked.is_active)
        self.assertIsNotNone(revoked.revoked_at)
        self.assertEqual(DatasetAccessGrant.objects.count(), 1)

        event = AuditEvent.objects.filter(
            action="dataset.grant_revoked"
        ).get()

        self.assertEqual(event.outcome, "success")
        self.assertEqual(event.organization, self.organization)
        self.assertEqual(event.actor, self.owner)
        self.assertEqual(event.target_id, str(self.grant.id))

    def test_admin_can_revoke_grant(self):
        self.owner_membership.role = "admin"
        self.owner_membership.save(update_fields=["role"])

        revoked = self.revoke()
        self.assertFalse(revoked.is_active)

    def test_unauthorized_role_cannot_revoke(self):
        self.owner_membership.role = "analyst"
        self.owner_membership.save(update_fields=["role"])

        with self.assertRaises(PermissionDenied):
            self.revoke()

        self.grant.refresh_from_db()
        self.assertTrue(self.grant.is_active)

    def test_cross_organization_grant_is_hidden(self):
        other = Organization.objects.create(
            name="Outside Revocation Company",
            slug="outside-revocation-company",
        )

        OrganizationMembership.objects.create(
            organization=other,
            user=self.owner,
            role="owner",
        )

        with self.assertRaises(Http404):
            self.revoke(organization=other)

        self.grant.refresh_from_db()
        self.assertTrue(self.grant.is_active)

    def test_duplicate_revocation_is_rejected(self):
        self.revoke()

        with self.assertRaises(ValidationError):
            self.revoke()

        self.assertEqual(
            AuditEvent.objects.filter(
                action="dataset.grant_revoked"
            ).count(),
            1,
        )

    def test_missing_grant_is_not_disclosed(self):
        with self.assertRaises(Http404):
            self.revoke(grant_id=uuid.uuid4())

        self.grant.refresh_from_db()
        self.assertTrue(self.grant.is_active)

    def test_audit_failure_rolls_back_revocation(self):
        with patch(
            "datasets.services.record_audit_event",
            side_effect=RuntimeError("Simulated audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.revoke()

        self.grant.refresh_from_db()
        self.assertTrue(self.grant.is_active)
        self.assertIsNone(self.grant.revoked_at)

        self.assertFalse(
            AuditEvent.objects.filter(
                action="dataset.grant_revoked"
            ).exists()
        )

    def test_revoked_grant_can_be_reactivated(self):
        self.revoke()

        restored = issue_dataset_access_grant(
            user=self.owner,
            organization=self.organization,
            dataset=self.dataset,
            membership=self.recipient_membership,
        )

        self.assertEqual(restored.id, self.grant.id)
        self.assertTrue(restored.is_active)
        self.assertIsNone(restored.revoked_at)
        self.assertEqual(DatasetAccessGrant.objects.count(), 1)

        self.assertEqual(
            AuditEvent.objects.filter(
                action="dataset.grant_reactivated"
            ).count(),
            1,
        )
