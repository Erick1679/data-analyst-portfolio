"""HTTP security tests for corporate audit history."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from organizations.models import Organization, OrganizationMembership

from .models import AuditEvent
from .services import record_audit_event


class AuditHistoryAPITests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="audit_api_user",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Audit API Company",
            slug="audit-api-company",
        )

        self.other_organization = Organization.objects.create(
            name="Other Audit API Company",
            slug="other-audit-api-company",
        )

        self.membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role="viewer",
        )

        self.event = record_audit_event(
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

        self.url = reverse(
            "organizations:auditlog:audit-history",
            kwargs={"organization_id": self.organization.id},
        )

        self.other_url = reverse(
            "organizations:auditlog:audit-history",
            kwargs={"organization_id": self.other_organization.id},
        )

    def set_role(self, role):
        self.membership.role = role
        self.membership.save(update_fields=["role"])

    def test_owner_can_access_audit_history(self):
        self.set_role("owner")
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

    def test_admin_can_access_audit_history(self):
        self.set_role("admin")
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    def test_auditor_can_access_audit_history(self):
        self.set_role("auditor")
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    def test_manager_denied(self):
        self.set_role("manager")
        self.client.force_login(self.user)

        self.assertEqual(
            self.client.get(self.url).status_code, 404
        )

    def test_analyst_denied(self):
        self.set_role("analyst")
        self.client.force_login(self.user)

        self.assertEqual(
            self.client.get(self.url).status_code, 404
        )

    def test_viewer_denied(self):
        self.client.force_login(self.user)

        self.assertEqual(
            self.client.get(self.url).status_code, 404
        )

    def test_cross_organization_access_denied(self):
        self.set_role("owner")
        self.client.force_login(self.user)

        self.assertEqual(
            self.client.get(self.other_url).status_code, 404
        )

    def test_anonymous_access_denied(self):
        self.assertEqual(
            self.client.get(self.url).status_code, 401
        )

    def test_inactive_membership_denied(self):
        self.set_role("owner")
        self.membership.is_active = False
        self.membership.save(update_fields=["is_active"])

        self.client.force_login(self.user)

        self.assertEqual(
            self.client.get(self.url).status_code, 404
        )

    def test_inactive_organization_denied(self):
        self.set_role("admin")
        self.organization.is_active = False
        self.organization.save(update_fields=["is_active"])

        self.client.force_login(self.user)

        self.assertEqual(
            self.client.get(self.url).status_code, 404
        )

    def test_post_method_not_allowed(self):
        self.set_role("owner")
        self.client.force_login(self.user)

        response = self.client.post(self.url, data={})

        self.assertEqual(response.status_code, 405)

    def test_response_limited_to_50_events(self):
        self.set_role("owner")
        self.client.force_login(self.user)

        AuditEvent.objects.bulk_create([
            AuditEvent(
                action="dataset.viewed",
                outcome="success",
                organization=self.organization,
                actor=self.user,
                target_type="dataset",
                target_id=f"dataset-{i}",
            )
            for i in range(55)
        ])

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 50)
        self.assertEqual(len(response.json()["results"]), 50)

        returned_ids = {
            event["id"] for event in response.json()["results"]
        }

        self.assertNotIn(str(self.other_event.id), returned_ids)
