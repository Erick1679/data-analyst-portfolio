"""Tests for tenant-scoped corporate audit history retrieval."""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from organizations.models import Organization, OrganizationMembership

from .models import AuditEvent
from .services import (
    list_organization_audit_events,
    record_audit_event,
)


class AuditRetrievalTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="audit_retrieval_user",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Audit Retrieval Company",
            slug="audit-retrieval-company",
        )

        self.other_organization = Organization.objects.create(
            name="Separate Audit Company",
            slug="separate-audit-company",
        )

        self.membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role="viewer",
        )

        self.own_event = record_audit_event(
            action="dataset.created",
            outcome="success",
            organization=self.organization,
            actor=self.user,
            target_type="dataset",
            target_id="own-dataset",
        )

        self.other_event = record_audit_event(
            action="dataset.created",
            outcome="success",
            organization=self.other_organization,
            actor=self.user,
            target_type="dataset",
            target_id="other-dataset",
        )

    def set_role(self, role):
        self.membership.role = role
        self.membership.save(update_fields=["role"])

    def get_events(self):
        return list(
            list_organization_audit_events(
                user=self.user,
                organization=self.organization,
            )
        )

    def test_owner_can_retrieve_own_audit_events(self):
        self.set_role("owner")
        self.assertIn(self.own_event, self.get_events())

    def test_admin_can_retrieve_own_audit_events(self):
        self.set_role("admin")
        self.assertIn(self.own_event, self.get_events())

    def test_auditor_can_retrieve_own_audit_events(self):
        self.set_role("auditor")
        self.assertIn(self.own_event, self.get_events())

    def test_manager_denied(self):
        self.set_role("manager")
        with self.assertRaises(PermissionDenied):
            self.get_events()

    def test_analyst_denied(self):
        self.set_role("analyst")
        with self.assertRaises(PermissionDenied):
            self.get_events()

    def test_viewer_denied(self):
        with self.assertRaises(PermissionDenied):
            self.get_events()

    def test_other_organization_events_excluded(self):
        self.set_role("owner")
        events = self.get_events()

        self.assertIn(self.own_event, events)
        self.assertNotIn(self.other_event, events)
        self.assertEqual(len(events), 1)

    def test_inactive_membership_denied(self):
        self.set_role("admin")
        self.membership.is_active = False
        self.membership.save(update_fields=["is_active"])

        with self.assertRaises(PermissionDenied):
            self.get_events()

    def test_inactive_organization_denied(self):
        self.set_role("owner")
        self.organization.is_active = False
        self.organization.save(update_fields=["is_active"])

        with self.assertRaises(PermissionDenied):
            self.get_events()

    def test_user_without_membership_denied(self):
        other_user = get_user_model().objects.create_user(
            username="audit_nonmember",
            password="local-test-password",
        )

        with self.assertRaises(PermissionDenied):
            list_organization_audit_events(
                user=other_user,
                organization=self.organization,
            )
