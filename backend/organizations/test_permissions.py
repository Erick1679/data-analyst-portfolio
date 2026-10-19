from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Organization, OrganizationMembership
from .permissions import has_organization_permission


class OrganizationPermissionTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="company_a_user",
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
            position="analyst",
        )

    def test_active_analyst_can_view_own_organization(self):
        self.assertTrue(
            has_organization_permission(
                self.user,
                self.company_a,
                "view_dashboard",
            )
        )

    def test_cross_organization_access_denied(self):
        self.assertFalse(
            has_organization_permission(
                self.user,
                self.company_b,
                "view_dashboard",
            )
        )

    def test_inactive_membership_denied(self):
        self.membership.is_active = False
        self.membership.save()

        self.assertFalse(
            has_organization_permission(
                self.user,
                self.company_a,
                "view_dashboard",
            )
        )

    def test_inactive_organization_denied(self):
        self.company_a.is_active = False
        self.company_a.save()

        self.assertFalse(
            has_organization_permission(
                self.user,
                self.company_a,
                "view_dashboard",
            )
        )

    def test_inactive_user_denied(self):
        self.user.is_active = False
        self.user.save()

        self.assertFalse(
            has_organization_permission(
                self.user,
                self.company_a,
                "view_dashboard",
            )
        )

    def test_analyst_cannot_manage_members(self):
        self.assertFalse(
            has_organization_permission(
                self.user,
                self.company_a,
                "manage_members",
            )
        )

    def test_job_position_does_not_override_access_role(self):
        self.membership.position = "ceo"
        self.membership.role = "viewer"
        self.membership.save()

        self.assertFalse(
            has_organization_permission(
                self.user,
                self.company_a,
                "manage_members",
            )
        )

    def test_unknown_permission_denied(self):
        self.assertFalse(
            has_organization_permission(
                self.user,
                self.company_a,
                "delete_all_data",
            )
        )

    def test_owner_can_manage_members(self):
        self.membership.role = "owner"
        self.membership.save()

        self.assertTrue(
            has_organization_permission(
                self.user,
                self.company_a,
                "manage_members",
            )
        )

    def test_anonymous_user_denied(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertFalse(
            has_organization_permission(
                AnonymousUser(),
                self.company_a,
                "view_dashboard",
            )
        )

    def test_viewer_cannot_create_reports(self):
        self.membership.role = "viewer"
        self.membership.save()

        self.assertFalse(
            has_organization_permission(
                self.user,
                self.company_a,
                "create_report",
            )
        )
