"""Dataset authorization security tests."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from organizations.models import (
    Organization,
    OrganizationMembership,
)
from .models import CorporateDataset
from .permissions import (
    can_create_dataset,
    can_view_dataset,
)


class DatasetPermissionTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dataset_security_user",
            password="local-test-password",
        )

        self.company_a = Organization.objects.create(
            name="Company A",
            slug="company-a",
        )
        self.company_b = Organization.objects.create(
            name="Company B",
            slug="company-b",
        )

        self.membership = OrganizationMembership.objects.create(
            organization=self.company_a,
            user=self.user,
            role="analyst",
        )

        self.dataset = CorporateDataset.objects.create(
            organization=self.company_a,
            created_by=self.user,
            name="Financial Overview",
            classification="confidential",
        )

    def test_analyst_can_view_own_confidential_dataset(self):
        self.assertTrue(
            can_view_dataset(self.user, self.dataset)
        )

    def test_cross_organization_dataset_access_denied(self):
        other_dataset = CorporateDataset.objects.create(
            organization=self.company_b,
            created_by=self.user,
            name="Company B Financial Records",
        )

        self.assertFalse(
            can_view_dataset(self.user, other_dataset)
        )

    def test_inactive_membership_denied(self):
        self.membership.is_active = False
        self.membership.save()

        self.assertFalse(
            can_view_dataset(self.user, self.dataset)
        )

    def test_inactive_organization_denied(self):
        self.company_a.is_active = False
        self.company_a.save()

        self.assertFalse(
            can_view_dataset(self.user, self.dataset)
        )

    def test_inactive_user_denied(self):
        self.user.is_active = False
        self.user.save()

        self.assertFalse(
            can_view_dataset(self.user, self.dataset)
        )

    def test_viewer_cannot_view_confidential_dataset(self):
        self.membership.role = "viewer"
        self.membership.save()

        self.assertFalse(
            can_view_dataset(self.user, self.dataset)
        )

    def test_viewer_can_view_internal_dataset(self):
        self.membership.role = "viewer"
        self.membership.save()

        self.dataset.classification = "internal"
        self.dataset.save()

        self.assertTrue(
            can_view_dataset(self.user, self.dataset)
        )

    def test_restricted_dataset_denied_even_to_owner(self):
        self.membership.role = "owner"
        self.membership.save()

        self.dataset.classification = "restricted"
        self.dataset.save()

        self.assertFalse(
            can_view_dataset(self.user, self.dataset)
        )

    def test_analyst_can_create_confidential_metadata(self):
        self.assertTrue(
            can_create_dataset(
                self.user,
                self.company_a,
                "confidential",
            )
        )

    def test_viewer_cannot_create_dataset(self):
        self.membership.role = "viewer"
        self.membership.save()

        self.assertFalse(
            can_create_dataset(
                self.user,
                self.company_a,
                "internal",
            )
        )

    def test_analyst_cannot_create_restricted_dataset(self):
        self.assertFalse(
            can_create_dataset(
                self.user,
                self.company_a,
                "restricted",
            )
        )

    def test_owner_can_create_restricted_metadata(self):
        self.membership.role = "owner"
        self.membership.save()

        self.assertTrue(
            can_create_dataset(
                self.user,
                self.company_a,
                "restricted",
            )
        )

    def test_cross_organization_creation_denied(self):
        self.assertFalse(
            can_create_dataset(
                self.user,
                self.company_b,
                "internal",
            )
        )

    def test_unknown_classification_denied(self):
        self.assertFalse(
            can_create_dataset(
                self.user,
                self.company_a,
                "publicly_unrestricted",
            )
        )
