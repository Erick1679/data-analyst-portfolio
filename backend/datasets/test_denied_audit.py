"""HTTP tests for denied dataset creation audit events."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from auditlog.models import AuditEvent
from organizations.models import Organization, OrganizationMembership

from .models import CorporateDataset


class DatasetDeniedAuditTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="denied_audit_user",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Denied Audit Company",
            slug="denied-audit-company",
        )

        self.other_organization = Organization.objects.create(
            name="Other Denied Audit Company",
            slug="other-denied-audit-company",
        )

        self.membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role="viewer",
        )

        self.url = self.make_url(self.organization)
        self.client.force_login(self.user)

    def make_url(self, organization):
        return reverse(
            "organizations:datasets:dataset-list",
            kwargs={"organization_id": organization.id},
        )

    def post_json(self, payload, url=None):
        return self.client.post(
            url or self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_viewer_denial_creates_audit_event(self):
        response = self.post_json({
            "name": "Viewer Rejected Report",
        })

        self.assertEqual(response.status_code, 403)
        self.assertEqual(CorporateDataset.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 1)

        event = AuditEvent.objects.get()
        self.assertEqual(event.action, "dataset.creation_denied")
        self.assertEqual(event.outcome, "denied")
        self.assertEqual(event.organization, self.organization)
        self.assertEqual(event.actor, self.user)

    def test_analyst_restricted_denial_is_audited(self):
        self.membership.role = "analyst"
        self.membership.save(update_fields=["role"])

        response = self.post_json({
            "name": "Restricted Attempt",
            "classification": "restricted",
        })

        self.assertEqual(response.status_code, 403)
        self.assertEqual(CorporateDataset.objects.count(), 0)
        self.assertEqual(
            AuditEvent.objects.filter(
                action="dataset.creation_denied"
            ).count(),
            1,
        )

    def test_success_has_no_denial_event(self):
        self.membership.role = "analyst"
        self.membership.save(update_fields=["role"])

        response = self.post_json({
            "name": "Authorized Report",
        })

        self.assertEqual(response.status_code, 201)
        self.assertEqual(CorporateDataset.objects.count(), 1)
        self.assertEqual(
            AuditEvent.objects.filter(
                action="dataset.created"
            ).count(),
            1,
        )
        self.assertFalse(
            AuditEvent.objects.filter(
                action="dataset.creation_denied"
            ).exists()
        )

    def test_invalid_input_does_not_create_denial_event(self):
        self.membership.role = "analyst"
        self.membership.save(update_fields=["role"])

        response = self.post_json({
            "name": ["invalid", "name"],
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(CorporateDataset.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_cross_organization_attempt_not_attributed(self):
        response = self.post_json(
            {"name": "Other Company Attempt"},
            url=self.make_url(self.other_organization),
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(CorporateDataset.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_inactive_membership_not_attributed(self):
        self.membership.is_active = False
        self.membership.save(update_fields=["is_active"])

        response = self.post_json({
            "name": "Inactive Membership Attempt",
        })

        self.assertEqual(response.status_code, 404)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_denial_event_excludes_submitted_metadata(self):
        sensitive_name = "Sensitive Project Name"
        sensitive_description = "Private corporate strategy"

        response = self.post_json({
            "name": sensitive_name,
            "description": sensitive_description,
        })

        self.assertEqual(response.status_code, 403)

        event = AuditEvent.objects.get()

        self.assertEqual(event.target_type, "dataset")
        self.assertEqual(event.target_id, "")

        recorded_values = " ".join([
            event.action,
            event.outcome,
            event.target_type,
            event.target_id,
        ])

        self.assertNotIn(sensitive_name, recorded_values)
        self.assertNotIn(sensitive_description, recorded_values)
