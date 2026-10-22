"""Tests for tenant-scoped audit access permissions."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from organizations.models import Organization, OrganizationMembership

from .permissions import can_view_audit_events


class AuditAccessPermissionTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="audit_permission_user",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Audit Permission Company",
            slug="audit-permission-company",
        )

        self.other_organization = Organization.objects.create(
            name="Other Audit Company",
            slug="other-audit-company",
        )

        self.membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role="viewer",
        )

    def set_role(self, role):
        self.membership.role = role
        self.membership.save(update_fields=["role"])

    def test_owner_allowed(self):
        self.set_role("owner")
        self.assertTrue(
            can_view_audit_events(self.user, self.organization)
        )

    def test_admin_allowed(self):
        self.set_role("admin")
        self.assertTrue(
            can_view_audit_events(self.user, self.organization)
        )

    def test_auditor_allowed(self):
        self.set_role("auditor")
        self.assertTrue(
            can_view_audit_events(self.user, self.organization)
        )

    def test_manager_denied(self):
        self.set_role("manager")
        self.assertFalse(
            can_view_audit_events(self.user, self.organization)
        )

    def test_editor_denied(self):
        self.set_role("editor")
        self.assertFalse(
            can_view_audit_events(self.user, self.organization)
        )

    def test_analyst_denied(self):
        self.set_role("analyst")
        self.assertFalse(
            can_view_audit_events(self.user, self.organization)
        )

    def test_viewer_denied(self):
        self.assertFalse(
            can_view_audit_events(self.user, self.organization)
        )

    def test_other_organization_denied(self):
        self.set_role("owner")
        self.assertFalse(
            can_view_audit_events(self.user, self.other_organization)
        )

    def test_inactive_membership_denied(self):
        self.set_role("admin")
        self.membership.is_active = False
        self.membership.save(update_fields=["is_active"])

        self.assertFalse(
            can_view_audit_events(self.user, self.organization)
        )

    def test_inactive_organization_denied(self):
        self.set_role("owner")
        self.organization.is_active = False
        self.organization.save(update_fields=["is_active"])

        self.assertFalse(
            can_view_audit_events(self.user, self.organization)
        )

    def test_inactive_user_denied(self):
        self.set_role("auditor")
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        self.assertFalse(
            can_view_audit_events(self.user, self.organization)
        )

    def test_invalid_organization_denied(self):
        self.set_role("owner")
        self.assertFalse(
            can_view_audit_events(self.user, None)
        )
