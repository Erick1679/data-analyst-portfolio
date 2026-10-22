"""Pagination security tests for corporate audit history."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from organizations.models import Organization, OrganizationMembership
from .models import AuditEvent


class AuditPaginationTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="audit_pagination_user",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Audit Pagination Company",
            slug="audit-pagination-company",
        )

        self.other_organization = Organization.objects.create(
            name="Other Pagination Company",
            slug="other-pagination-company",
        )

        self.membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role="auditor",
        )

        AuditEvent.objects.bulk_create([
            AuditEvent(
                organization=self.organization,
                actor=self.user,
                action="dataset.viewed",
                outcome="success",
                target_type="dataset",
                target_id=f"own-{i}",
            )
            for i in range(105)
        ])

        AuditEvent.objects.bulk_create([
            AuditEvent(
                organization=self.other_organization,
                actor=self.user,
                action="dataset.viewed",
                outcome="success",
                target_type="dataset",
                target_id=f"other-{i}",
            )
            for i in range(5)
        ])

        self.url = reverse(
            "organizations:auditlog:audit-history",
            kwargs={"organization_id": self.organization.id},
        )

        self.client.force_login(self.user)

    def test_default_page_is_one(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["page"], 1)
        self.assertEqual(response.json()["count"], 50)

    def test_second_page_returns_50_events(self):
        response = self.client.get(self.url, {"page": "2"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["page"], 2)
        self.assertEqual(response.json()["count"], 50)

    def test_third_page_returns_remaining_events(self):
        response = self.client.get(self.url, {"page": "3"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 5)

    def test_invalid_text_page_rejected(self):
        response = self.client.get(self.url, {"page": "abc"})

        self.assertEqual(response.status_code, 400)

    def test_zero_page_rejected(self):
        response = self.client.get(self.url, {"page": "0"})

        self.assertEqual(response.status_code, 400)

    def test_negative_page_rejected(self):
        response = self.client.get(self.url, {"page": "-1"})

        self.assertEqual(response.status_code, 400)

    def test_excessively_long_page_rejected(self):
        response = self.client.get(
            self.url,
            {"page": "99999999999999999999"},
        )

        self.assertEqual(response.status_code, 400)

    def test_page_beyond_records_is_empty(self):
        response = self.client.get(self.url, {"page": "5"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)
        self.assertEqual(response.json()["results"], [])

    def test_other_organization_records_excluded(self):
        for page in ("1", "2", "3"):
            response = self.client.get(
                self.url,
                {"page": page},
            )

            self.assertEqual(response.status_code, 200)

            for event in response.json()["results"]:
                self.assertTrue(
                    event["target_id"].startswith("own-")
                )

    def test_unauthorized_user_cannot_access_page_two(self):
        self.membership.role = "viewer"
        self.membership.save(update_fields=["role"])

        response = self.client.get(self.url, {"page": "2"})

        self.assertEqual(response.status_code, 404)
