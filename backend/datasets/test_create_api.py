"""Security and validation tests for corporate dataset creation."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from organizations.models import Organization, OrganizationMembership
from .models import CorporateDataset


class DatasetCreationAPITests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dataset_creation_user",
            password="local-test-password",
        )

        self.company_a = Organization.objects.create(
            name="Creation Company A",
            slug="creation-company-a",
        )

        self.company_b = Organization.objects.create(
            name="Creation Company B",
            slug="creation-company-b",
        )

        self.membership = OrganizationMembership.objects.create(
            organization=self.company_a,
            user=self.user,
            role="analyst",
        )

        self.url = reverse(
            "organizations:datasets:dataset-list",
            kwargs={"organization_id": self.company_a.id},
        )

        self.other_url = reverse(
            "organizations:datasets:dataset-list",
            kwargs={"organization_id": self.company_b.id},
        )

    def post_json(self, payload, url=None):
        return self.client.post(
            url or self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_analyst_creates_confidential_dataset(self):
        self.client.force_login(self.user)

        response = self.post_json({
            "name": "Quarterly Revenue",
            "category": "financial",
            "classification": "confidential",
        })

        self.assertEqual(response.status_code, 201)
        self.assertEqual(CorporateDataset.objects.count(), 1)

        dataset = CorporateDataset.objects.get()
        self.assertEqual(dataset.organization, self.company_a)
        self.assertEqual(dataset.created_by, self.user)

    def test_viewer_cannot_create_dataset(self):
        self.membership.role = "viewer"
        self.membership.save()

        self.client.force_login(self.user)

        response = self.post_json({
            "name": "Unauthorized Dataset",
        })

        self.assertEqual(response.status_code, 403)
        self.assertEqual(CorporateDataset.objects.count(), 0)

    def test_cross_organization_creation_denied(self):
        self.client.force_login(self.user)

        response = self.post_json(
            {"name": "Cross Company Dataset"},
            url=self.other_url,
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(CorporateDataset.objects.count(), 0)

    def test_anonymous_creation_denied(self):
        response = self.post_json({
            "name": "Anonymous Dataset",
        })

        self.assertEqual(response.status_code, 401)
        self.assertEqual(CorporateDataset.objects.count(), 0)

    def test_analyst_cannot_create_restricted_dataset(self):
        self.client.force_login(self.user)

        response = self.post_json({
            "name": "Restricted Dataset",
            "classification": "restricted",
        })

        self.assertEqual(response.status_code, 403)
        self.assertEqual(CorporateDataset.objects.count(), 0)

    def test_owner_can_create_restricted_metadata(self):
        self.membership.role = "owner"
        self.membership.save()

        self.client.force_login(self.user)

        response = self.post_json({
            "name": "Restricted Metadata",
            "classification": "restricted",
        })

        self.assertEqual(response.status_code, 201)
        self.assertEqual(CorporateDataset.objects.count(), 1)

    def test_duplicate_dataset_name_rejected(self):
        self.client.force_login(self.user)

        payload = {"name": "Duplicate Report"}

        first = self.post_json(payload)
        second = self.post_json(payload)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(CorporateDataset.objects.count(), 1)

    def test_invalid_category_rejected(self):
        self.client.force_login(self.user)

        response = self.post_json({
            "name": "Invalid Category Dataset",
            "category": "unknown-category",
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(CorporateDataset.objects.count(), 0)

    def test_invalid_json_rejected(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            data="{invalid-json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(CorporateDataset.objects.count(), 0)

    def test_unknown_fields_rejected(self):
        self.client.force_login(self.user)

        response = self.post_json({
            "name": "Unexpected Field Dataset",
            "organization": str(self.company_b.id),
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(CorporateDataset.objects.count(), 0)

    def test_json_array_rejected(self):
        self.client.force_login(self.user)

        response = self.post_json([
            {"name": "Invalid Payload"}
        ])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(CorporateDataset.objects.count(), 0)

    def test_oversized_request_rejected(self):
        self.client.force_login(self.user)

        response = self.post_json({
            "name": "Oversized Dataset",
            "description": "A" * 17000,
        })

        self.assertEqual(response.status_code, 413)
        self.assertEqual(CorporateDataset.objects.count(), 0)

    def test_inactive_membership_denied(self):
        self.membership.is_active = False
        self.membership.save()

        self.client.force_login(self.user)

        response = self.post_json({
            "name": "Inactive Membership Dataset",
        })

        self.assertEqual(response.status_code, 404)
        self.assertEqual(CorporateDataset.objects.count(), 0)

    def test_invalid_name_type_rejected(self):
        self.client.force_login(self.user)

        response = self.post_json({
            "name": ["not", "a", "string"],
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(CorporateDataset.objects.count(), 0)
