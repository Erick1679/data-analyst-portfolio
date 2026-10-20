"""Security tests for dataset grant administration permissions."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from organizations.models import Organization, OrganizationMembership

from .permissions import can_manage_dataset_grants


class DatasetGrantPermissionTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="grant_permission_user",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Grant Permission Company",
            slug="grant-permission-company",
        )

        self.membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role="viewer",
        )

    def test_owner_can_manage_grants(self):
        self.membership.role = "owner"
        self.membership.save(update_fields=["role"])

        self.assertTrue(
            can_manage_dataset_grants(self.user, self.organization)
        )

    def test_admin_can_manage_grants(self):
        self.membership.role = "admin"
        self.membership.save(update_fields=["role"])

        self.assertTrue(
            can_manage_dataset_grants(self.user, self.organization)
        )

    def test_other_roles_cannot_manage_grants(self):
        for role in (
            "manager", "editor", "analyst", "auditor", "viewer"
        ):
            with self.subTest(role=role):
                self.membership.role = role
                self.membership.save(update_fields=["role"])

                self.assertFalse(
                    can_manage_dataset_grants(
                        self.user, self.organization
                    )
                )

    def test_inactive_membership_cannot_manage_grants(self):
        self.membership.role = "owner"
        self.membership.is_active = False
        self.membership.save(
            update_fields=["role", "is_active"]
        )

        self.assertFalse(
            can_manage_dataset_grants(self.user, self.organization)
        )

    def test_inactive_organization_cannot_manage_grants(self):
        self.membership.role = "admin"
        self.membership.save(update_fields=["role"])
        self.organization.is_active = False
        self.organization.save(update_fields=["is_active"])

        self.assertFalse(
            can_manage_dataset_grants(self.user, self.organization)
        )

    def test_nonmember_cannot_manage_grants(self):
        outsider = get_user_model().objects.create_user(
            username="grant_permission_outsider",
            password="local-test-password",
        )

        self.assertFalse(
            can_manage_dataset_grants(outsider, self.organization)
        )
