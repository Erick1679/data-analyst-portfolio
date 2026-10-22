"""CSRF security tests for corporate dataset creation."""

import json

from django.contrib.auth import get_user_model
from django.middleware.csrf import _get_new_csrf_string
from django.test import Client, TestCase
from django.urls import reverse

from organizations.models import Organization, OrganizationMembership
from .models import CorporateDataset


class DatasetCreationCSRFTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="csrf_dataset_user",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="CSRF Test Company",
            slug="csrf-test-company",
        )

        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role="analyst",
        )

        self.url = reverse(
            "organizations:datasets:dataset-list",
            kwargs={"organization_id": self.organization.id},
        )

        self.csrf_client = Client(enforce_csrf_checks=True)

    def post_json(self, name, **extra):
        return self.csrf_client.post(
            self.url,
            data=json.dumps({"name": name}),
            content_type="application/json",
            **extra,
        )

    def test_authenticated_post_without_csrf_rejected(self):
        self.csrf_client.force_login(self.user)

        response = self.post_json("Missing CSRF Token")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(CorporateDataset.objects.count(), 0)

    def test_authenticated_post_with_valid_csrf_allowed(self):
        self.csrf_client.force_login(self.user)

        token = _get_new_csrf_string()
        self.csrf_client.cookies["csrftoken"] = token

        response = self.post_json(
            "Valid CSRF Token",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(CorporateDataset.objects.count(), 1)

    def test_anonymous_post_without_csrf_rejected(self):
        response = self.post_json("Anonymous CSRF Attempt")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(CorporateDataset.objects.count(), 0)
