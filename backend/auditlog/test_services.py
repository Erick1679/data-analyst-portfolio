"""Tests for controlled audit event recording."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from organizations.models import Organization

from .models import AuditEvent
from .services import record_audit_event


class AuditEventServiceTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="audit_service_user",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Audit Test Company",
            slug="audit-test-company",
        )

    def record(self, **overrides):
        values = {
            "action": "dataset.created",
            "outcome": "success",
            "organization": self.organization,
            "actor": self.user,
            "target_type": "dataset",
            "target_id": "test-dataset-123",
        }
        values.update(overrides)
        return record_audit_event(**values)

    def test_valid_event_created(self):
        event = self.record()

        self.assertEqual(AuditEvent.objects.count(), 1)
        self.assertEqual(event.organization, self.organization)
        self.assertEqual(event.actor, self.user)
        self.assertEqual(event.action, "dataset.created")
        self.assertEqual(event.outcome, "success")
        self.assertIsNotNone(event.created_at)

    def test_denied_event_created(self):
        event = self.record(
            action="dataset.creation_denied",
            outcome="denied",
        )

        self.assertEqual(event.outcome, "denied")
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_event_without_actor_allowed(self):
        event = self.record(actor=None)

        self.assertIsNone(event.actor)
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_event_without_organization_allowed(self):
        event = self.record(organization=None)

        self.assertIsNone(event.organization)
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_invalid_action_rejected(self):
        with self.assertRaises(ValidationError):
            self.record(action="unsupported.action")

        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_invalid_action_type_rejected(self):
        with self.assertRaises(ValidationError):
            self.record(action=["dataset.created"])

        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_invalid_outcome_rejected(self):
        with self.assertRaises(ValidationError):
            self.record(outcome="unknown")

        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_invalid_organization_rejected(self):
        with self.assertRaises(ValidationError):
            self.record(organization="not-an-organization")

        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_unsaved_organization_rejected(self):
        unsaved = Organization(
            name="Unsaved Audit Company",
            slug="unsaved-audit-company",
        )

        with self.assertRaises(ValidationError):
            self.record(organization=unsaved)

        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_invalid_actor_rejected(self):
        with self.assertRaises(ValidationError):
            self.record(actor="not-a-user")

        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_invalid_target_type_rejected(self):
        with self.assertRaises(ValidationError):
            self.record(target_type=["dataset"])

        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_oversized_target_id_rejected(self):
        with self.assertRaises(ValidationError):
            self.record(target_id="x" * 101)

        self.assertEqual(AuditEvent.objects.count(), 0)
