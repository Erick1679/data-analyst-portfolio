"""Transaction-boundary tests for denied audit events."""

import json

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TransactionTestCase
from django.urls import reverse

from auditlog.models import AuditEvent
from organizations.models import Organization, OrganizationMembership

from .models import CorporateDataset


class DatasetAuditTransactionTests(TransactionTestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="audit_transaction_user",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Audit Transaction Company",
            slug="audit-transaction-company",
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

    def test_denial_audit_survives_normal_request(self):
        response = self.client.post(
            self.url,
            data=json.dumps({"name": "Denied Dataset"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(CorporateDataset.objects.count(), 0)
        self.assertEqual(
            AuditEvent.objects.filter(
                action="dataset.creation_denied"
            ).count(),
            1,
        )

    def test_outer_rollback_removes_denial_audit(self):
        try:
            with transaction.atomic():
                response = self.client.post(
                    self.url,
                    data=json.dumps({"name": "Rolled Back Dataset"}),
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, 403)
                self.assertEqual(
                    AuditEvent.objects.filter(
                        action="dataset.creation_denied"
                    ).count(),
                    1,
                )

                raise RuntimeError("Simulated outer transaction failure")
        except RuntimeError:
            pass

        self.assertEqual(CorporateDataset.objects.count(), 0)

        # Documents the current limitation:
        # an outer rollback also removes the denial audit.
        self.assertEqual(
            AuditEvent.objects.filter(
                action="dataset.creation_denied"
            ).count(),
            0,
        )
