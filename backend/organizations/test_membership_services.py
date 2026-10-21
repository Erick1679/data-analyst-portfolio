"""Security tests for corporate membership-management services."""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from auditlog.models import AuditEvent

from .models import Organization, OrganizationMembership


class MembershipServiceTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            username="membership_service_owner",
            password="local-test-password",
        )

        self.admin = User.objects.create_user(
            username="membership_service_admin",
            password="local-test-password",
        )

        self.recipient = User.objects.create_user(
            username="membership_service_recipient",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Membership Service Company",
            slug="membership-service-company",
        )

        self.other_organization = Organization.objects.create(
            name="Outside Membership Service Company",
            slug="outside-membership-service-company",
        )

        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role="owner",
        )

        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.admin,
            role="admin",
        )

    def create_member(self, *, actor=None, organization=None, role="analyst"):
        from .services import create_organization_membership

        return create_organization_membership(
            actor=actor or self.owner,
            organization=organization or self.organization,
            user=self.recipient,
            role=role,
        )

    def test_owner_creates_membership_with_audit(self):
        membership = self.create_member()

        self.assertEqual(membership.role, "analyst")
        self.assertTrue(membership.is_active)
        self.assertEqual(membership.organization, self.organization)

        self.assertTrue(
            AuditEvent.objects.filter(
                action="membership.changed",
                outcome="success",
                organization=self.organization,
                actor=self.owner,
            ).exists()
        )

    def test_admin_can_create_analyst_membership(self):
        membership = self.create_member(actor=self.admin)

        self.assertEqual(membership.role, "analyst")
        self.assertEqual(membership.user, self.recipient)

    def test_admin_cannot_appoint_owner(self):
        with self.assertRaises(PermissionDenied):
            self.create_member(
                actor=self.admin,
                role="owner",
            )

        self.assertFalse(
            OrganizationMembership.objects.filter(
                user=self.recipient,
                organization=self.organization,
            ).exists()
        )

    def test_duplicate_membership_rejected(self):
        self.create_member()

        with self.assertRaises(ValidationError):
            self.create_member()

        self.assertEqual(
            OrganizationMembership.objects.filter(
                user=self.recipient,
                organization=self.organization,
            ).count(),
            1,
        )

    def test_other_organization_cannot_be_managed(self):
        with self.assertRaises(PermissionDenied):
            self.create_member(
                organization=self.other_organization,
            )

        self.assertEqual(
            OrganizationMembership.objects.filter(
                user=self.recipient,
            ).count(),
            0,
        )

    def test_inactive_recipient_rejected(self):
        self.recipient.is_active = False
        self.recipient.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            self.create_member()

        self.assertFalse(
            OrganizationMembership.objects.filter(
                organization=self.organization,
                user=self.recipient,
            ).exists()
        )

    def test_invalid_membership_role_rejected(self):
        with self.assertRaises(ValidationError):
            self.create_member(role="superuser")

        self.assertFalse(
            OrganizationMembership.objects.filter(
                organization=self.organization,
                user=self.recipient,
            ).exists()
        )

    def test_unauthorized_actor_cannot_create_membership(self):
        with self.assertRaises(PermissionDenied):
            self.create_member(actor=self.recipient)

        self.assertFalse(
            OrganizationMembership.objects.filter(
                organization=self.organization,
                user=self.recipient,
            ).exists()
        )

    def test_owner_can_appoint_another_owner(self):
        membership = self.create_member(role="owner")

        self.assertEqual(membership.role, "owner")
        self.assertTrue(membership.is_active)

    def test_audit_failure_rolls_back_membership_creation(self):
        from unittest.mock import patch

        with patch(
            "organizations.services.record_audit_event",
            side_effect=RuntimeError("Simulated audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.create_member()

        self.assertFalse(
            OrganizationMembership.objects.filter(
                organization=self.organization,
                user=self.recipient,
            ).exists()
        )

        self.assertEqual(AuditEvent.objects.count(), 0)


class MembershipRoleChangeTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            username="role_change_owner",
            password="local-test-password",
        )
        self.admin = User.objects.create_user(
            username="role_change_admin",
            password="local-test-password",
        )
        self.analyst = User.objects.create_user(
            username="role_change_analyst",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Role Change Company",
            slug="role-change-company",
        )

        self.other_organization = Organization.objects.create(
            name="Outside Role Change Company",
            slug="outside-role-change-company",
        )

        self.owner_membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role="owner",
        )

        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.admin,
            role="admin",
        )

        self.analyst_membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.analyst,
            role="analyst",
        )

    def change_role(self, membership=None, actor=None, role="viewer"):
        from .services import change_organization_membership_role

        return change_organization_membership_role(
            actor=actor or self.owner,
            organization=self.organization,
            membership_id=(
                membership.id if membership is not None
                else self.analyst_membership.id
            ),
            role=role,
        )

    def test_owner_can_change_analyst_role(self):
        membership = self.change_role(role="editor")

        self.assertEqual(membership.role, "editor")

        self.assertTrue(
            AuditEvent.objects.filter(
                action="membership.changed",
                organization=self.organization,
                actor=self.owner,
            ).exists()
        )

    def test_admin_cannot_promote_member_to_owner(self):
        with self.assertRaises(PermissionDenied):
            self.change_role(actor=self.admin, role="owner")

        self.analyst_membership.refresh_from_db()
        self.assertEqual(self.analyst_membership.role, "analyst")

    def test_analyst_cannot_change_membership_role(self):
        with self.assertRaises(PermissionDenied):
            self.change_role(actor=self.analyst, role="editor")

        self.analyst_membership.refresh_from_db()
        self.assertEqual(self.analyst_membership.role, "analyst")

    def test_cross_organization_membership_hidden(self):
        outside = OrganizationMembership.objects.create(
            organization=self.other_organization,
            user=self.analyst,
            role="viewer",
        )

        from django.http import Http404

        with self.assertRaises(Http404):
            self.change_role(membership=outside, role="editor")

        outside.refresh_from_db()
        self.assertEqual(outside.role, "viewer")

    def test_last_active_owner_cannot_be_demoted(self):
        with self.assertRaises(ValidationError):
            self.change_role(
                membership=self.owner_membership,
                role="admin",
            )

        self.owner_membership.refresh_from_db()
        self.assertEqual(self.owner_membership.role, "owner")

    def test_owner_can_be_demoted_when_another_owner_exists(self):
        other_owner = get_user_model().objects.create_user(
            username="role_change_second_owner",
            password="local-test-password",
        )

        OrganizationMembership.objects.create(
            organization=self.organization,
            user=other_owner,
            role="owner",
        )

        changed = self.change_role(
            membership=self.owner_membership,
            role="admin",
        )

        self.assertEqual(changed.role, "admin")

        self.assertTrue(
            OrganizationMembership.objects.filter(
                organization=self.organization,
                role="owner",
                is_active=True,
                user__is_active=True,
            ).exists()
        )

    def test_admin_cannot_demote_existing_owner(self):
        with self.assertRaises(PermissionDenied):
            self.change_role(
                membership=self.owner_membership,
                actor=self.admin,
                role="analyst",
            )

        self.owner_membership.refresh_from_db()
        self.assertEqual(self.owner_membership.role, "owner")

    def test_duplicate_role_change_rejected(self):
        with self.assertRaises(ValidationError):
            self.change_role(role="analyst")

        self.analyst_membership.refresh_from_db()
        self.assertEqual(self.analyst_membership.role, "analyst")

    def test_invalid_role_change_rejected(self):
        with self.assertRaises(ValidationError):
            self.change_role(role="superuser")

        self.analyst_membership.refresh_from_db()
        self.assertEqual(self.analyst_membership.role, "analyst")

    def test_role_change_audit_failure_rolls_back(self):
        from unittest.mock import patch

        with patch(
            "organizations.services.record_audit_event",
            side_effect=RuntimeError("Simulated audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.change_role(role="editor")

        self.analyst_membership.refresh_from_db()
        self.assertEqual(self.analyst_membership.role, "analyst")
        self.assertEqual(AuditEvent.objects.count(), 0)


class MembershipDeactivationTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            username="deactivation_owner",
            password="local-test-password",
        )
        self.admin = User.objects.create_user(
            username="deactivation_admin",
            password="local-test-password",
        )
        self.analyst = User.objects.create_user(
            username="deactivation_analyst",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Deactivation Company",
            slug="deactivation-company",
        )
        self.other_organization = Organization.objects.create(
            name="Outside Deactivation Company",
            slug="outside-deactivation-company",
        )

        self.owner_membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role="owner",
        )

        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.admin,
            role="admin",
        )

        self.analyst_membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.analyst,
            role="analyst",
        )

    def deactivate(self, membership=None, actor=None):
        from .services import deactivate_organization_membership

        return deactivate_organization_membership(
            actor=actor or self.owner,
            organization=self.organization,
            membership_id=(
                membership.id if membership is not None
                else self.analyst_membership.id
            ),
        )

    def test_owner_can_deactivate_analyst(self):
        membership = self.deactivate()

        self.assertFalse(membership.is_active)

        self.analyst_membership.refresh_from_db()
        self.assertFalse(self.analyst_membership.is_active)

        self.assertTrue(
            AuditEvent.objects.filter(
                action="membership.changed",
                outcome="success",
                organization=self.organization,
                actor=self.owner,
            ).exists()
        )

    def test_admin_can_deactivate_analyst(self):
        membership = self.deactivate(actor=self.admin)

        self.assertFalse(membership.is_active)

    def test_admin_cannot_deactivate_owner(self):
        with self.assertRaises(PermissionDenied):
            self.deactivate(
                membership=self.owner_membership,
                actor=self.admin,
            )

        self.owner_membership.refresh_from_db()
        self.assertTrue(self.owner_membership.is_active)

    def test_last_active_owner_cannot_be_deactivated(self):
        with self.assertRaises(ValidationError):
            self.deactivate(membership=self.owner_membership)

        self.owner_membership.refresh_from_db()
        self.assertTrue(self.owner_membership.is_active)

    def test_cross_organization_deactivation_hidden(self):
        from django.http import Http404

        outside = OrganizationMembership.objects.create(
            organization=self.other_organization,
            user=self.analyst,
            role="viewer",
        )

        with self.assertRaises(Http404):
            self.deactivate(membership=outside)

        outside.refresh_from_db()
        self.assertTrue(outside.is_active)

    def test_repeated_deactivation_rejected(self):
        self.deactivate()

        with self.assertRaises(ValidationError):
            self.deactivate()

        self.assertEqual(
            AuditEvent.objects.filter(
                action="membership.changed",
                organization=self.organization,
            ).count(),
            1,
        )

    def test_analyst_cannot_deactivate_membership(self):
        with self.assertRaises(PermissionDenied):
            self.deactivate(actor=self.analyst)

        self.analyst_membership.refresh_from_db()
        self.assertTrue(self.analyst_membership.is_active)

    def test_owner_deactivation_allowed_with_another_owner(self):
        second_owner = get_user_model().objects.create_user(
            username="deactivation_second_owner",
            password="local-test-password",
        )

        OrganizationMembership.objects.create(
            organization=self.organization,
            user=second_owner,
            role="owner",
        )

        membership = self.deactivate(
            membership=self.owner_membership,
        )

        self.assertFalse(membership.is_active)

        self.assertTrue(
            OrganizationMembership.objects.filter(
                organization=self.organization,
                role="owner",
                is_active=True,
                user__is_active=True,
            ).exists()
        )

    def test_deactivation_audit_failure_rolls_back(self):
        from unittest.mock import patch

        with patch(
            "organizations.services.record_audit_event",
            side_effect=RuntimeError("Simulated audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.deactivate()

        self.analyst_membership.refresh_from_db()
        self.assertTrue(self.analyst_membership.is_active)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_missing_membership_not_found(self):
        from django.http import Http404

        from .services import deactivate_organization_membership

        with self.assertRaises(Http404):
            deactivate_organization_membership(
                actor=self.owner,
                organization=self.organization,
                membership_id=999999999,
            )

        self.analyst_membership.refresh_from_db()
        self.assertTrue(self.analyst_membership.is_active)
