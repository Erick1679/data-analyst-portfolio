"""HTTP integration tests for restricted dataset access grants."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from auditlog.models import AuditEvent
from organizations.models import Organization, OrganizationMembership

from .models import CorporateDataset
from .services import (
    issue_dataset_access_grant,
    revoke_dataset_access_grant,
)


class RestrictedDatasetHTTPTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            username="restricted_http_owner",
            password="local-test-password",
        )
        self.recipient = User.objects.create_user(
            username="restricted_http_recipient",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Restricted HTTP Company",
            slug="restricted-http-company",
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
            name="Restricted HTTP Dataset",
            classification="restricted",
        )

        self.list_url = reverse(
            "organizations:datasets:dataset-list",
            kwargs={"organization_id": self.organization.id},
        )

        self.detail_url = reverse(
            "organizations:datasets:dataset-detail",
            kwargs={
                "organization_id": self.organization.id,
                "dataset_id": self.dataset.id,
            },
        )

        self.client.force_login(self.recipient)

    def issue(self):
        return issue_dataset_access_grant(
            user=self.owner,
            organization=self.organization,
            dataset=self.dataset,
            membership=self.membership,
        )

    def test_granted_dataset_appears_in_http_listing(self):
        self.issue()

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        ids = {
            item["id"]
            for item in response.json()["results"]
        }
        self.assertIn(str(self.dataset.id), ids)

    def test_granted_dataset_detail_returns_success(self):
        self.issue()

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["id"],
            str(self.dataset.id),
        )

    def test_missing_grant_denies_restricted_detail(self):
        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 404)

        event = AuditEvent.objects.get()
        self.assertEqual(event.action, "dataset.access_denied")

    def test_revocation_removes_http_access(self):
        grant = self.issue()

        self.assertEqual(
            self.client.get(self.detail_url).status_code,
            200,
        )

        revoke_dataset_access_grant(
            user=self.owner,
            organization=self.organization,
            grant_id=grant.id,
        )

        self.assertEqual(
            self.client.get(self.detail_url).status_code,
            404,
        )

        response = self.client.get(self.list_url)
        ids = {
            item["id"]
            for item in response.json()["results"]
        }

        self.assertNotIn(str(self.dataset.id), ids)

    def test_cross_organization_request_is_hidden(self):
        other = Organization.objects.create(
            name="Outside Restricted HTTP Company",
            slug="outside-restricted-http-company",
        )

        url = reverse(
            "organizations:datasets:dataset-detail",
            kwargs={
                "organization_id": other.id,
                "dataset_id": self.dataset.id,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_success_and_denial_audits_are_recorded(self):
        self.client.get(self.detail_url)
        self.issue()
        self.client.get(self.detail_url)

        actions = set(
            AuditEvent.objects.values_list(
                "action",
                flat=True,
            )
        )

        self.assertIn("dataset.access_denied", actions)
        self.assertIn("dataset.grant_created", actions)
        self.assertIn("dataset.viewed", actions)
