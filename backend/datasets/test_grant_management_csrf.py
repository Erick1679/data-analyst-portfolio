"""CSRF protection tests for dataset grant-management endpoints."""

import json

from django.contrib.auth import get_user_model
from django.middleware.csrf import _get_new_csrf_string
from django.test import Client, TestCase
from django.urls import reverse

from organizations.models import Organization, OrganizationMembership

from .models import CorporateDataset, DatasetAccessGrant
from .services import issue_dataset_access_grant


class GrantManagementCSRFTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            username="grant_csrf_owner",
            password="local-test-password",
        )

        self.recipient = User.objects.create_user(
            username="grant_csrf_recipient",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Grant CSRF Company",
            slug="grant-csrf-company",
        )

        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role="owner",
        )

        self.membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.recipient,
            role="analyst",
        )

        self.dataset = CorporateDataset.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name="Grant CSRF Dataset",
            classification="restricted",
        )

        self.grant_url = reverse(
            "organizations:datasets:grant-list",
            kwargs={
                "organization_id": self.organization.id,
                "dataset_id": self.dataset.id,
            },
        )

        self.csrf_client = Client(enforce_csrf_checks=True)
        self.csrf_client.force_login(self.owner)

    def enable_csrf(self):
        token = _get_new_csrf_string()
        self.csrf_client.cookies["csrftoken"] = token
        return token

    def post_grant(self, **extra):
        return self.csrf_client.post(
            self.grant_url,
            data=json.dumps({
                "membership_id": self.membership.id,
            }),
            content_type="application/json",
            **extra,
        )

    def revoke_url(self, grant):
        return reverse(
            "organizations:datasets:grant-revoke",
            kwargs={
                "organization_id": self.organization.id,
                "dataset_id": self.dataset.id,
                "grant_id": grant.id,
            },
        )

    def test_issue_without_csrf_rejected(self):
        response = self.post_grant()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(DatasetAccessGrant.objects.count(), 0)

    def test_issue_with_valid_csrf_allowed(self):
        token = self.enable_csrf()

        response = self.post_grant(
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(DatasetAccessGrant.objects.count(), 1)

    def test_revoke_without_csrf_rejected(self):
        grant = issue_dataset_access_grant(
            user=self.owner,
            organization=self.organization,
            dataset=self.dataset,
            membership=self.membership,
        )

        response = self.csrf_client.post(
            self.revoke_url(grant),
        )

        self.assertEqual(response.status_code, 403)

        grant.refresh_from_db()
        self.assertTrue(grant.is_active)
        self.assertIsNone(grant.revoked_at)

    def test_revoke_with_valid_csrf_allowed(self):
        grant = issue_dataset_access_grant(
            user=self.owner,
            organization=self.organization,
            dataset=self.dataset,
            membership=self.membership,
        )

        token = self.enable_csrf()

        response = self.csrf_client.post(
            self.revoke_url(grant),
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 200)

        grant.refresh_from_db()
        self.assertFalse(grant.is_active)
        self.assertIsNotNone(grant.revoked_at)
