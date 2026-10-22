"""Security tests for tenant-scoped restricted dataset listings."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from organizations.models import Organization, OrganizationMembership

from .models import CorporateDataset
from .services import (
    issue_dataset_access_grant,
    list_accessible_datasets,
    revoke_dataset_access_grant,
)


class RestrictedDatasetListingTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            username="restricted_listing_owner",
            password="local-test-password",
        )
        self.recipient = User.objects.create_user(
            username="restricted_listing_recipient",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Restricted Listing Company",
            slug="restricted-listing-company",
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

        self.restricted = CorporateDataset.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name="Restricted Listing Dataset",
            classification="restricted",
        )

        self.internal = CorporateDataset.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name="Internal Listing Dataset",
            classification="internal",
        )

        self.confidential = CorporateDataset.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name="Confidential Listing Dataset",
            classification="confidential",
        )

    def visible_ids(self, user=None, organization=None):
        return set(
            list_accessible_datasets(
                user=user or self.recipient,
                organization=organization or self.organization,
            ).values_list("id", flat=True)
        )

    def issue(self):
        return issue_dataset_access_grant(
            user=self.owner,
            organization=self.organization,
            dataset=self.restricted,
            membership=self.membership,
        )

    def test_active_grant_includes_restricted_dataset(self):
        self.issue()
        self.assertIn(self.restricted.id, self.visible_ids())

    def test_missing_grant_excludes_restricted_dataset(self):
        self.assertNotIn(self.restricted.id, self.visible_ids())

    def test_revocation_removes_restricted_dataset(self):
        grant = self.issue()
        self.assertIn(self.restricted.id, self.visible_ids())

        revoke_dataset_access_grant(
            user=self.owner,
            organization=self.organization,
            grant_id=grant.id,
        )

        self.assertNotIn(self.restricted.id, self.visible_ids())

    def test_inactive_membership_excludes_all_datasets(self):
        self.issue()
        self.membership.is_active = False
        self.membership.save(update_fields=["is_active"])

        self.assertEqual(self.visible_ids(), set())

    def test_inactive_user_excludes_all_datasets(self):
        self.issue()
        self.recipient.is_active = False
        self.recipient.save(update_fields=["is_active"])

        self.assertEqual(self.visible_ids(), set())

    def test_inactive_organization_excludes_all_datasets(self):
        self.issue()
        self.organization.is_active = False
        self.organization.save(update_fields=["is_active"])

        self.assertEqual(self.visible_ids(), set())

    def test_revoked_timestamp_excludes_restricted_dataset(self):
        grant = self.issue()
        grant.revoked_at = timezone.now()
        grant.save(update_fields=["revoked_at"])

        self.assertNotIn(self.restricted.id, self.visible_ids())

    def test_existing_classification_permissions_preserved(self):
        visible = self.visible_ids()

        self.assertIn(self.internal.id, visible)
        self.assertIn(self.confidential.id, visible)
        self.assertNotIn(self.restricted.id, visible)

        self.membership.role = "viewer"
        self.membership.save(update_fields=["role"])

        visible = self.visible_ids()
        self.assertIn(self.internal.id, visible)
        self.assertNotIn(self.confidential.id, visible)
        self.assertNotIn(self.restricted.id, visible)

    def test_cross_organization_datasets_remain_excluded(self):
        self.issue()

        other = Organization.objects.create(
            name="Outside Restricted Listing Company",
            slug="outside-restricted-listing-company",
        )

        outside_dataset = CorporateDataset.objects.create(
            organization=other,
            created_by=self.owner,
            name="Outside Restricted Listing Dataset",
            classification="restricted",
        )

        self.assertNotIn(outside_dataset.id, self.visible_ids())
        self.assertIn(self.restricted.id, self.visible_ids())
