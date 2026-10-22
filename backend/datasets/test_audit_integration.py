"""Integration tests for dataset creation audit recording."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from auditlog.models import AuditEvent
from organizations.models import Organization, OrganizationMembership

from .models import CorporateDataset
from .services import create_dataset


class DatasetAuditIntegrationTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dataset_audit_integration_user",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Audit Integration Company",
            slug="audit-integration-company",
        )

        self.membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role="analyst",
        )

    def create(self, name="Audit Integration Dataset", **extra):
        return create_dataset(
            user=self.user,
            organization=self.organization,
            name=name,
            **extra,
        )

    def test_success_creates_dataset_and_audit_event(self):
        dataset = self.create()

        self.assertEqual(CorporateDataset.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 1)

        event = AuditEvent.objects.get()
        self.assertEqual(event.target_id, str(dataset.id))

    def test_success_audit_metadata_is_correct(self):
        dataset = self.create()

        event = AuditEvent.objects.get()

        self.assertEqual(event.action, "dataset.created")
        self.assertEqual(event.outcome, "success")
        self.assertEqual(event.organization, self.organization)
        self.assertEqual(event.actor, self.user)
        self.assertEqual(event.target_type, "dataset")
        self.assertEqual(event.target_id, str(dataset.id))

    def test_audit_failure_rolls_back_dataset_creation(self):
        with patch(
            "datasets.services.record_audit_event",
            side_effect=RuntimeError("Simulated audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.create()

        self.assertEqual(CorporateDataset.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_unauthorized_creation_has_no_success_event(self):
        self.membership.role = "viewer"
        self.membership.save(update_fields=["role"])

        with self.assertRaises(PermissionDenied):
            self.create()

        self.assertEqual(CorporateDataset.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_invalid_dataset_has_no_success_event(self):
        with self.assertRaises(ValidationError):
            self.create(name="")

        self.assertEqual(CorporateDataset.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_audit_events_are_attributed_to_correct_organization(self):
        other_organization = Organization.objects.create(
            name="Second Audit Integration Company",
            slug="second-audit-integration-company",
        )

        OrganizationMembership.objects.create(
            organization=other_organization,
            user=self.user,
            role="analyst",
        )

        first = self.create(name="First Company Dataset")

        second = create_dataset(
            user=self.user,
            organization=other_organization,
            name="Second Company Dataset",
        )

        first_event = AuditEvent.objects.get(
            target_id=str(first.id)
        )
        second_event = AuditEvent.objects.get(
            target_id=str(second.id)
        )

        self.assertEqual(
            first_event.organization, self.organization
        )
        self.assertEqual(
            second_event.organization, other_organization
        )
        self.assertEqual(AuditEvent.objects.count(), 2)
