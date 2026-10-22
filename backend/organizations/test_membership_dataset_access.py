"""Membership lifecycle integration tests for dataset access."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from datasets.models import CorporateDataset
from datasets.permissions import (
    can_create_dataset,
    can_view_dataset,
)
from datasets.services import issue_dataset_access_grant

from .models import Organization, OrganizationMembership
from .services import (
    change_organization_membership_role,
    deactivate_organization_membership,
)


class MembershipDatasetAccessTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            username="lifecycle_owner",
            password="local-test-password",
        )
        self.member = User.objects.create_user(
            username="lifecycle_member",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Lifecycle Integration Company",
            slug="lifecycle-integration-company",
        )

        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role="owner",
        )

        self.membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.member,
            role="analyst",
        )

        self.internal_dataset = CorporateDataset.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name="Lifecycle Internal Dataset",
            classification="internal",
        )

        self.confidential_dataset = CorporateDataset.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name="Lifecycle Confidential Dataset",
            classification="confidential",
        )

        self.restricted_dataset = CorporateDataset.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name="Lifecycle Restricted Dataset",
            classification="restricted",
        )

    def test_deactivation_immediately_removes_internal_access(self):
        self.assertTrue(
            can_view_dataset(self.member, self.internal_dataset)
        )

        deactivate_organization_membership(
            actor=self.owner,
            organization=self.organization,
            membership_id=self.membership.pk,
        )

        self.assertFalse(
            can_view_dataset(self.member, self.internal_dataset)
        )

    def test_role_demotion_removes_confidential_access(self):
        self.assertTrue(
            can_view_dataset(self.member, self.confidential_dataset)
        )

        change_organization_membership_role(
            actor=self.owner,
            organization=self.organization,
            membership_id=self.membership.pk,
            role="viewer",
        )

        self.assertFalse(
            can_view_dataset(self.member, self.confidential_dataset)
        )
        self.assertFalse(
            can_create_dataset(
                self.member,
                self.organization,
                "confidential",
            )
        )

        # Viewers retain access to internal datasets.
        self.assertTrue(
            can_view_dataset(self.member, self.internal_dataset)
        )

    def test_deactivation_revokes_restricted_grants(self):
        grant = issue_dataset_access_grant(
            user=self.owner,
            organization=self.organization,
            dataset=self.restricted_dataset,
            membership=self.membership,
        )

        self.assertTrue(grant.is_active)
        self.assertIsNone(grant.revoked_at)

        deactivate_organization_membership(
            actor=self.owner,
            organization=self.organization,
            membership_id=self.membership.pk,
        )

        grant.refresh_from_db()

        self.assertFalse(grant.is_active)
        self.assertIsNotNone(grant.revoked_at)

        self.assertFalse(
            can_view_dataset(self.member, self.restricted_dataset)
        )

    def test_restricted_grant_cannot_bypass_deactivation(self):
        grant = issue_dataset_access_grant(
            user=self.owner,
            organization=self.organization,
            dataset=self.restricted_dataset,
            membership=self.membership,
        )

        self.assertTrue(
            can_view_dataset(self.member, self.restricted_dataset)
        )

        deactivate_organization_membership(
            actor=self.owner,
            organization=self.organization,
            membership_id=self.membership.pk,
        )

        grant.refresh_from_db()

        # Preserve the grant record while revoking its access.
        self.assertFalse(grant.is_active)
        self.assertIsNotNone(grant.revoked_at)

        self.assertFalse(
            can_view_dataset(self.member, self.restricted_dataset)
        )

    def test_multiple_restricted_grants_revoked(self):
        from datasets.models import DatasetAccessGrant

        second_dataset = CorporateDataset.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name="Second Restricted Lifecycle Dataset",
            classification="restricted",
        )

        first_grant = issue_dataset_access_grant(
            user=self.owner,
            organization=self.organization,
            dataset=self.restricted_dataset,
            membership=self.membership,
        )

        second_grant = issue_dataset_access_grant(
            user=self.owner,
            organization=self.organization,
            dataset=second_dataset,
            membership=self.membership,
        )

        deactivate_organization_membership(
            actor=self.owner,
            organization=self.organization,
            membership_id=self.membership.pk,
        )

        for grant in (first_grant, second_grant):
            grant.refresh_from_db()
            self.assertFalse(grant.is_active)
            self.assertIsNotNone(grant.revoked_at)

        self.assertEqual(
            DatasetAccessGrant.objects.filter(
                membership=self.membership,
                is_active=True,
            ).count(),
            0,
        )

    def test_deactivation_records_grant_and_membership_audits(self):
        from auditlog.models import AuditEvent

        grant = issue_dataset_access_grant(
            user=self.owner,
            organization=self.organization,
            dataset=self.restricted_dataset,
            membership=self.membership,
        )

        deactivate_organization_membership(
            actor=self.owner,
            organization=self.organization,
            membership_id=self.membership.pk,
        )

        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                actor=self.owner,
                action="dataset.grant_revoked",
                target_id=str(grant.pk),
                outcome="success",
            ).count(),
            1,
        )

        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                actor=self.owner,
                action="membership.changed",
                target_id=str(self.membership.pk),
                outcome="success",
            ).count(),
            1,
        )

    def test_grant_revocation_audit_failure_rolls_back_everything(self):
        from unittest.mock import patch

        from auditlog.models import AuditEvent

        grant = issue_dataset_access_grant(
            user=self.owner,
            organization=self.organization,
            dataset=self.restricted_dataset,
            membership=self.membership,
        )

        with patch(
            "organizations.services.record_audit_event",
            side_effect=RuntimeError("Simulated audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                deactivate_organization_membership(
                    actor=self.owner,
                    organization=self.organization,
                    membership_id=self.membership.pk,
                )

        self.membership.refresh_from_db()
        grant.refresh_from_db()

        self.assertTrue(self.membership.is_active)
        self.assertTrue(grant.is_active)
        self.assertIsNone(grant.revoked_at)

        self.assertFalse(
            AuditEvent.objects.filter(
                action="dataset.grant_revoked",
                target_id=str(grant.pk),
            ).exists()
        )
