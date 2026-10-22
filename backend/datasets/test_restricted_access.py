"""Security tests for restricted dataset viewing permissions."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from organizations.models import Organization, OrganizationMembership

from .models import CorporateDataset, DatasetAccessGrant
from .permissions import can_view_dataset
from .services import (
    issue_dataset_access_grant,
    revoke_dataset_access_grant,
)


class RestrictedDatasetAccessTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            username="restricted_access_owner",
            password="local-test-password",
        )
        self.recipient = User.objects.create_user(
            username="restricted_access_recipient",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Restricted Access Company",
            slug="restricted-access-company",
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
            name="Restricted Access Dataset",
            classification="restricted",
        )

    def issue(self):
        return issue_dataset_access_grant(
            user=self.owner,
            organization=self.organization,
            dataset=self.dataset,
            membership=self.recipient_membership,
        )

    def test_active_grant_allows_restricted_view(self):
        self.issue()

        self.assertTrue(
            can_view_dataset(self.recipient, self.dataset)
        )

    def test_without_grant_access_is_denied(self):
        self.assertFalse(
            can_view_dataset(self.recipient, self.dataset)
        )

    def test_owner_has_no_automatic_restricted_access(self):
        self.assertFalse(
            can_view_dataset(self.owner, self.dataset)
        )

    def test_revocation_immediately_removes_access(self):
        grant = self.issue()

        self.assertTrue(
            can_view_dataset(self.recipient, self.dataset)
        )

        revoke_dataset_access_grant(
            user=self.owner,
            organization=self.organization,
            grant_id=grant.id,
        )

        self.assertFalse(
            can_view_dataset(self.recipient, self.dataset)
        )

    def test_inactive_membership_blocks_granted_access(self):
        self.issue()

        self.recipient_membership.is_active = False
        self.recipient_membership.save(update_fields=["is_active"])

        self.assertFalse(
            can_view_dataset(self.recipient, self.dataset)
        )

    def test_inactive_user_blocks_granted_access(self):
        self.issue()

        self.recipient.is_active = False
        self.recipient.save(update_fields=["is_active"])

        self.assertFalse(
            can_view_dataset(self.recipient, self.dataset)
        )

    def test_inactive_organization_blocks_granted_access(self):
        self.issue()

        self.organization.is_active = False
        self.organization.save(update_fields=["is_active"])

        self.assertFalse(
            can_view_dataset(self.recipient, self.dataset)
        )

    def test_revoked_timestamp_blocks_access(self):
        grant = self.issue()

        grant.revoked_at = timezone.now()
        grant.save(update_fields=["revoked_at"])

        self.assertFalse(
            can_view_dataset(self.recipient, self.dataset)
        )

    def test_other_organization_grant_cannot_authorize_access(self):
        self.issue()

        other = Organization.objects.create(
            name="Other Restricted Access Company",
            slug="other-restricted-access-company",
        )

        outside_user = get_user_model().objects.create_user(
            username="restricted_access_outsider",
            password="local-test-password",
        )

        OrganizationMembership.objects.create(
            organization=other,
            user=outside_user,
            role="owner",
        )

        self.assertFalse(
            can_view_dataset(outside_user, self.dataset)
        )
