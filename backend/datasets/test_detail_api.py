"""HTTP security tests for individual dataset metadata retrieval."""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from organizations.models import Organization, OrganizationMembership
from .models import CorporateDataset


class DatasetDetailAPITests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dataset_detail_user",
            password="local-test-password",
        )

        self.company_a = Organization.objects.create(
            name="Company A",
            slug="detail-company-a",
        )
        self.company_b = Organization.objects.create(
            name="Company B",
            slug="detail-company-b",
        )

        self.membership = OrganizationMembership.objects.create(
            organization=self.company_a,
            user=self.user,
            role="analyst",
        )

        self.confidential = CorporateDataset.objects.create(
            organization=self.company_a,
            created_by=self.user,
            name="Confidential Financial Report",
            classification="confidential",
        )

        self.restricted = CorporateDataset.objects.create(
            organization=self.company_a,
            created_by=self.user,
            name="Restricted Financial Report",
            classification="restricted",
        )

        self.other_company_dataset = CorporateDataset.objects.create(
            organization=self.company_b,
            created_by=self.user,
            name="Other Company Report",
            classification="internal",
        )

    def url(self, organization, dataset_id):
        return reverse(
            "organizations:datasets:dataset-detail",
            kwargs={
                "organization_id": organization.id,
                "dataset_id": dataset_id,
            },
        )

    def test_analyst_can_retrieve_own_confidential_dataset(self):
        self.client.force_login(self.user)

        response = self.client.get(
            self.url(self.company_a, self.confidential.id)
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["id"],
            str(self.confidential.id),
        )

    def test_viewer_cannot_retrieve_confidential_dataset(self):
        self.membership.role = "viewer"
        self.membership.save()

        self.client.force_login(self.user)

        response = self.client.get(
            self.url(self.company_a, self.confidential.id)
        )

        self.assertEqual(response.status_code, 404)

    def test_owner_cannot_retrieve_restricted_dataset(self):
        self.membership.role = "owner"
        self.membership.save()

        self.client.force_login(self.user)

        response = self.client.get(
            self.url(self.company_a, self.restricted.id)
        )

        self.assertEqual(response.status_code, 404)

    def test_cross_organization_retrieval_denied(self):
        self.client.force_login(self.user)

        response = self.client.get(
            self.url(self.company_a, self.other_company_dataset.id)
        )

        self.assertEqual(response.status_code, 404)

    def test_anonymous_access_denied(self):
        response = self.client.get(
            self.url(self.company_a, self.confidential.id)
        )

        self.assertEqual(response.status_code, 401)

    def test_inactive_membership_denied(self):
        self.membership.is_active = False
        self.membership.save()

        self.client.force_login(self.user)

        response = self.client.get(
            self.url(self.company_a, self.confidential.id)
        )

        self.assertEqual(response.status_code, 404)

    def test_unknown_dataset_returns_404(self):
        self.client.force_login(self.user)

        response = self.client.get(
            self.url(self.company_a, uuid.uuid4())
        )

        self.assertEqual(response.status_code, 404)

    def test_post_method_not_allowed(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url(self.company_a, self.confidential.id),
            data={},
        )

        self.assertEqual(response.status_code, 405)
