"""HTTP security tests for corporate dashboard access."""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Organization, OrganizationMembership


class CorporateDashboardTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="corporate_test_user",
            password="local-test-password",
        )

        self.company_a = Organization.objects.create(
            name="Company A",
            slug="company-a",
        )

        self.company_b = Organization.objects.create(
            name="Company B",
            slug="company-b",
        )

        self.membership = OrganizationMembership.objects.create(
            organization=self.company_a,
            user=self.user,
            role="analyst",
        )

    def dashboard_url(self, organization):
        return reverse(
            "organizations:corporate-dashboard",
            kwargs={"organization_id": organization.id},
        )

    def test_authorized_member_can_access_dashboard(self):
        self.client.force_login(self.user)

        response = self.client.get(
            self.dashboard_url(self.company_a)
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["organization_id"],
            str(self.company_a.id),
        )

    def test_unauthenticated_user_denied(self):
        response = self.client.get(
            self.dashboard_url(self.company_a)
        )

        self.assertEqual(response.status_code, 401)

    def test_cross_organization_access_denied(self):
        self.client.force_login(self.user)

        response = self.client.get(
            self.dashboard_url(self.company_b)
        )

        self.assertEqual(response.status_code, 404)

    def test_inactive_membership_denied(self):
        self.membership.is_active = False
        self.membership.save()

        self.client.force_login(self.user)

        response = self.client.get(
            self.dashboard_url(self.company_a)
        )

        self.assertEqual(response.status_code, 404)

    def test_inactive_organization_denied(self):
        self.company_a.is_active = False
        self.company_a.save()

        self.client.force_login(self.user)

        response = self.client.get(
            self.dashboard_url(self.company_a)
        )

        self.assertEqual(response.status_code, 404)

    def test_inactive_user_denied(self):
        self.user.is_active = False
        self.user.save()

        self.client.force_login(self.user)

        response = self.client.get(
            self.dashboard_url(self.company_a)
        )

        self.assertNotEqual(response.status_code, 200)
        self.assertIn(response.status_code, (401, 404))

    def test_nonexistent_organization_returns_404(self):
        self.client.force_login(self.user)

        url = reverse(
            "organizations:corporate-dashboard",
            kwargs={"organization_id": uuid.uuid4()},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)
