"""Failure-handling tests for denied dataset creation auditing."""

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from auditlog.models import AuditEvent
from organizations.models import Organization, OrganizationMembership

from .models import CorporateDataset


class DatasetAuditFailureTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="audit_failure_user",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Audit Failure Company",
            slug="audit-failure-company",
        )

        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role="viewer",
        )

        self.url = reverse(
            "organizations:datasets:dataset-list",
            kwargs={"organization_id": self.organization.id},
        )

        self.client.force_login(self.user)

    def test_denial_audit_failure_does_not_create_dataset(self):
        with patch(
            "datasets.views.record_audit_event",
            side_effect=RuntimeError("Simulated audit storage failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    self.url,
                    data=json.dumps({
                        "name": "Unauthorized Dataset",
                    }),
                    content_type="application/json",
                )

        self.assertEqual(CorporateDataset.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_denial_response_when_audit_storage_succeeds(self):
        response = self.client.post(
            self.url,
            data=json.dumps({
                "name": "Unauthorized Dataset",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(CorporateDataset.objects.count(), 0)
        self.assertEqual(
            AuditEvent.objects.filter(
                action="dataset.creation_denied",
                outcome="denied",
            ).count(),
            1,
        )
