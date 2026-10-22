"""Boundary tests for accurate audit history pagination."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from organizations.models import Organization, OrganizationMembership
from .models import AuditEvent


class AuditPaginationBoundaryTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="audit_boundary_user",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Audit Boundary Company",
            slug="audit-boundary-company",
        )

        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role="auditor",
        )

        self.url = reverse(
            "organizations:auditlog:audit-history",
            kwargs={"organization_id": self.organization.id},
        )

        self.client.force_login(self.user)

    def create_events(self, count):
        AuditEvent.objects.bulk_create([
            AuditEvent(
                organization=self.organization,
                actor=self.user,
                action="dataset.viewed",
                outcome="success",
                target_type="dataset",
                target_id=f"boundary-{i}",
            )
            for i in range(count)
        ])

    def check_page(self, count, page, expected_count, has_next):
        self.create_events(count)

        response = self.client.get(
            self.url,
            {"page": str(page)},
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(data["page"], page)
        self.assertEqual(data["count"], expected_count)
        self.assertEqual(data["has_next"], has_next)
        self.assertLessEqual(len(data["results"]), 50)

    def test_25_records_first_page_has_no_next(self):
        self.check_page(25, 1, 25, False)

    def test_50_records_first_page_has_no_next(self):
        self.check_page(50, 1, 50, False)

    def test_51_records_first_page_has_next(self):
        self.check_page(51, 1, 50, True)

    def test_100_records_second_page_has_no_next(self):
        self.check_page(100, 2, 50, False)

    def test_105_records_second_page_has_next(self):
        self.check_page(105, 2, 50, True)
