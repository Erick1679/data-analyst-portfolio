"""HTTP security tests for dataset detail access auditing."""

from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from auditlog.models import AuditEvent
from organizations.models import Organization, OrganizationMembership

from .models import CorporateDataset


class DatasetAccessAuditTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="access_audit_user",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Access Audit Company",
            slug="access-audit-company",
        )

        self.other_organization = Organization.objects.create(
            name="Other Access Audit Company",
            slug="other-access-audit-company",
        )

        self.membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role="analyst",
        )

        self.client.force_login(self.user)

        self.dataset = CorporateDataset.objects.create(
            organization=self.organization,
            created_by=self.user,
            name="Confidential Audit Dataset",
            description="Private corporate metadata",
            classification="confidential",
        )

    def detail_url(self, organization, dataset_id):
        return reverse(
            "organizations:datasets:dataset-detail",
            kwargs={
                "organization_id": organization.id,
                "dataset_id": dataset_id,
            },
        )

    def test_authorized_view_creates_success_event(self):
        response = self.client.get(
            self.detail_url(self.organization, self.dataset.id)
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(AuditEvent.objects.count(), 1)

        event = AuditEvent.objects.get()
        self.assertEqual(event.action, "dataset.viewed")
        self.assertEqual(event.outcome, "success")
        self.assertEqual(event.organization, self.organization)
        self.assertEqual(event.actor, self.user)
        self.assertEqual(event.target_id, str(self.dataset.id))

    def test_viewer_denial_creates_denied_event(self):
        self.membership.role = "viewer"
        self.membership.save(update_fields=["role"])

        response = self.client.get(
            self.detail_url(self.organization, self.dataset.id)
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(AuditEvent.objects.count(), 1)
        self.assertEqual(
            AuditEvent.objects.get().action,
            "dataset.access_denied",
        )

    def test_restricted_dataset_remains_inaccessible(self):
        self.dataset.classification = "restricted"
        self.dataset.save(update_fields=["classification"])

        response = self.client.get(
            self.detail_url(self.organization, self.dataset.id)
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            AuditEvent.objects.filter(
                action="dataset.access_denied",
                outcome="denied",
            ).count(),
            1,
        )

    def test_nonmember_access_is_not_attributed(self):
        response = self.client.get(
            self.detail_url(
                self.other_organization,
                self.dataset.id,
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_missing_dataset_creates_no_event(self):
        response = self.client.get(
            self.detail_url(self.organization, uuid.uuid4())
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_inactive_membership_creates_no_event(self):
        self.membership.is_active = False
        self.membership.save(update_fields=["is_active"])

        response = self.client.get(
            self.detail_url(self.organization, self.dataset.id)
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_audit_record_excludes_sensitive_metadata(self):
        response = self.client.get(
            self.detail_url(self.organization, self.dataset.id)
        )

        self.assertEqual(response.status_code, 200)

        event = AuditEvent.objects.get()
        recorded = " ".join([
            event.action,
            event.outcome,
            event.target_type,
            event.target_id,
        ])

        self.assertNotIn(self.dataset.name, recorded)
        self.assertNotIn(self.dataset.description, recorded)

    def test_audit_write_failure_blocks_success_response(self):
        with patch(
            "datasets.views.record_audit_event",
            side_effect=RuntimeError("Simulated audit write failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.client.get(
                    self.detail_url(
                        self.organization,
                        self.dataset.id,
                    )
                )

        self.assertEqual(AuditEvent.objects.count(), 0)
