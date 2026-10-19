"""HTTP security tests for corporate dataset listing."""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from organizations.models import Organization, OrganizationMembership
from .models import CorporateDataset


class DatasetListingAPITests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dataset_api_user",
            password="local-test-password",
        )

        self.company_a = Organization.objects.create(
            name="Company A",
            slug="api-company-a",
        )
        self.company_b = Organization.objects.create(
            name="Company B",
            slug="api-company-b",
        )

        self.membership = OrganizationMembership.objects.create(
            organization=self.company_a,
            user=self.user,
            role="analyst",
        )

        self.internal = CorporateDataset.objects.create(
            organization=self.company_a,
            created_by=self.user,
            name="Internal Data",
            classification="internal",
        )
        self.confidential = CorporateDataset.objects.create(
            organization=self.company_a,
            created_by=self.user,
            name="Confidential Data",
            classification="confidential",
        )
        self.restricted = CorporateDataset.objects.create(
            organization=self.company_a,
            created_by=self.user,
            name="Restricted Data",
            classification="restricted",
        )
        self.other_company = CorporateDataset.objects.create(
            organization=self.company_b,
            created_by=self.user,
            name="Other Company Data",
            classification="internal",
        )

    def url(self, organization):
        return reverse(
            "organizations:datasets:dataset-list",
            kwargs={"organization_id": organization.id},
        )

    def test_analyst_sees_only_permitted_own_datasets(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url(self.company_a))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)

        returned_ids = {
            item["id"] for item in response.json()["results"]
        }

        self.assertEqual(
            returned_ids,
            {str(self.internal.id), str(self.confidential.id)},
        )

    def test_viewer_sees_internal_only(self):
        self.membership.role = "viewer"
        self.membership.save()

        self.client.force_login(self.user)
        response = self.client.get(self.url(self.company_a))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(
            response.json()["results"][0]["id"],
            str(self.internal.id),
        )

    def test_other_organization_access_denied(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url(self.company_b))
        self.assertEqual(response.status_code, 404)

    def test_anonymous_access_denied(self):
        response = self.client.get(self.url(self.company_a))
        self.assertEqual(response.status_code, 401)

    def test_inactive_membership_denied(self):
        self.membership.is_active = False
        self.membership.save()

        self.client.force_login(self.user)
        response = self.client.get(self.url(self.company_a))

        self.assertEqual(response.status_code, 404)

    def test_inactive_organization_denied(self):
        self.company_a.is_active = False
        self.company_a.save()

        self.client.force_login(self.user)
        response = self.client.get(self.url(self.company_a))

        self.assertEqual(response.status_code, 404)

    def test_unknown_organization_returns_404(self):
        self.client.force_login(self.user)

        url = reverse(
            "organizations:datasets:dataset-list",
            kwargs={"organization_id": uuid.uuid4()},
        )

        self.assertEqual(self.client.get(url).status_code, 404)

    def test_post_without_json_is_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post(
            self.url(self.company_a),
            data={},
        )
        self.assertEqual(response.status_code, 415)

    def test_delete_method_is_not_allowed(self):
        self.client.force_login(self.user)
        response = self.client.delete(
            self.url(self.company_a),
        )
        self.assertEqual(response.status_code, 405)
