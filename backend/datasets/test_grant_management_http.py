from unittest import skipUnless
"""HTTP security tests for dataset grant management."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from auditlog.models import AuditEvent
from organizations.models import Organization, OrganizationMembership

from .models import CorporateDataset, DatasetAccessGrant


class GrantManagementHTTPTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            username="grant_http_owner",
            password="local-test-password",
        )
        self.analyst = User.objects.create_user(
            username="grant_http_analyst",
            password="local-test-password",
        )
        self.outsider = User.objects.create_user(
            username="grant_http_outsider",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Grant HTTP Company",
            slug="grant-http-company",
        )

        self.other_organization = Organization.objects.create(
            name="Other Grant HTTP Company",
            slug="other-grant-http-company",
        )

        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role="owner",
        )

        self.analyst_membership = (
            OrganizationMembership.objects.create(
                organization=self.organization,
                user=self.analyst,
                role="analyst",
            )
        )

        self.dataset = CorporateDataset.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name="Grant Management Dataset",
            classification="restricted",
        )

        self.grant_url = reverse(
            "organizations:datasets:grant-list",
            kwargs={
                "organization_id": self.organization.id,
                "dataset_id": self.dataset.id,
            },
        )

    def post_grant(self, membership_id=None):
        return self.client.post(
            self.grant_url,
            data=json.dumps({
                "membership_id": (
                    membership_id
                    if membership_id is not None
                    else self.analyst_membership.id
                ),
            }),
            content_type="application/json",
        )

    def test_owner_can_issue_grant(self):
        self.client.force_login(self.owner)

        response = self.post_grant()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(DatasetAccessGrant.objects.count(), 1)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="dataset.grant_created",
            ).exists()
        )

    def test_analyst_cannot_issue_grant(self):
        self.client.force_login(self.analyst)

        response = self.post_grant()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(DatasetAccessGrant.objects.count(), 0)

    def test_anonymous_user_cannot_issue_grant(self):
        response = self.post_grant()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(DatasetAccessGrant.objects.count(), 0)

    def test_nonmember_cannot_access_organization(self):
        self.client.force_login(self.outsider)

        response = self.post_grant()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(DatasetAccessGrant.objects.count(), 0)

    def test_owner_can_revoke_grant(self):
        self.client.force_login(self.owner)

        created = self.post_grant()
        grant_id = created.json()["id"]

        revoke_url = reverse(
            "organizations:datasets:grant-revoke",
            kwargs={
                "organization_id": self.organization.id,
                "dataset_id": self.dataset.id,
                "grant_id": grant_id,
            },
        )

        response = self.client.post(revoke_url)

        self.assertEqual(response.status_code, 200)

        grant = DatasetAccessGrant.objects.get(id=grant_id)
        self.assertFalse(grant.is_active)
        self.assertIsNotNone(grant.revoked_at)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="dataset.grant_revoked",
            ).exists()
        )

    def test_reissued_revoked_grant_is_reactivated(self):
        self.client.force_login(self.owner)

        created = self.post_grant()
        grant_id = created.json()["id"]

        revoke_url = reverse(
            "organizations:datasets:grant-revoke",
            kwargs={
                "organization_id": self.organization.id,
                "dataset_id": self.dataset.id,
                "grant_id": grant_id,
            },
        )

        self.client.post(revoke_url)

        response = self.post_grant()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["id"],
            grant_id,
        )
        self.assertTrue(response.json()["is_active"])
        self.assertEqual(DatasetAccessGrant.objects.count(), 1)
        self.assertEqual(
            AuditEvent.objects.filter(
                action="dataset.grant_reactivated",
            ).count(),
            1,
        )

    def test_malformed_json_rejected(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.grant_url,
            data="{invalid-json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(DatasetAccessGrant.objects.count(), 0)

    def test_invalid_membership_id_rejected(self):
        self.client.force_login(self.owner)

        response = self.post_grant(membership_id=True)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(DatasetAccessGrant.objects.count(), 0)

    def test_duplicate_active_grant_rejected(self):
        self.client.force_login(self.owner)

        first = self.post_grant()
        second = self.post_grant()

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(DatasetAccessGrant.objects.count(), 1)

    def test_cross_organization_membership_hidden(self):
        other_user = get_user_model().objects.create_user(
            username="grant_http_other_member",
            password="local-test-password",
        )

        other_membership = OrganizationMembership.objects.create(
            organization=self.other_organization,
            user=other_user,
            role="analyst",
        )

        self.client.force_login(self.owner)

        response = self.post_grant(
            membership_id=other_membership.id,
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(DatasetAccessGrant.objects.count(), 0)

    def test_revocation_with_wrong_dataset_hidden(self):
        self.client.force_login(self.owner)

        created = self.post_grant()

        self.assertEqual(created.status_code, 201)

        other_dataset = CorporateDataset.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name="Another Restricted Dataset",
            classification="restricted",
        )

        wrong_url = reverse(
            "organizations:datasets:grant-revoke",
            kwargs={
                "organization_id": self.organization.id,
                "dataset_id": other_dataset.id,
                "grant_id": created.json()["id"],
            },
        )

        response = self.client.post(wrong_url)

        self.assertEqual(response.status_code, 404)

        grant = DatasetAccessGrant.objects.get(
            id=created.json()["id"],
        )

        self.assertTrue(grant.is_active)
        self.assertIsNone(grant.revoked_at)

    def test_issue_get_method_rejected(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.grant_url)

        self.assertEqual(response.status_code, 405)
        self.assertEqual(DatasetAccessGrant.objects.count(), 0)

    def test_issue_put_method_rejected(self):
        self.client.force_login(self.owner)

        response = self.client.put(
            self.grant_url,
            data=json.dumps({
                "membership_id": self.analyst_membership.id,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 405)
        self.assertEqual(DatasetAccessGrant.objects.count(), 0)

    def test_issue_oversized_request_rejected(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.grant_url,
            data=json.dumps({
                "membership_id": self.analyst_membership.id,
                "padding": "A" * 17000,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(DatasetAccessGrant.objects.count(), 0)

    def test_issue_unknown_field_rejected(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.grant_url,
            data=json.dumps({
                "membership_id": self.analyst_membership.id,
                "role": "owner",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(DatasetAccessGrant.objects.count(), 0)

    def test_issue_wrong_content_type_rejected(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.grant_url,
            data="membership_id=1",
            content_type="text/plain",
        )

        self.assertEqual(response.status_code, 415)
        self.assertEqual(DatasetAccessGrant.objects.count(), 0)

    def test_revoke_get_method_rejected(self):
        self.client.force_login(self.owner)

        created = self.post_grant()
        self.assertEqual(created.status_code, 201)

        grant_id = created.json()["id"]

        revoke_url = reverse(
            "organizations:datasets:grant-revoke",
            kwargs={
                "organization_id": self.organization.id,
                "dataset_id": self.dataset.id,
                "grant_id": grant_id,
            },
        )

        response = self.client.get(revoke_url)

        self.assertEqual(response.status_code, 405)

        grant = DatasetAccessGrant.objects.get(id=grant_id)
        self.assertTrue(grant.is_active)

    def test_inactive_owner_account_denied(self):
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])

        self.client.force_login(self.owner)

        response = self.post_grant()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(DatasetAccessGrant.objects.count(), 0)

    def test_inactive_owner_membership_denied(self):
        membership = OrganizationMembership.objects.get(
            organization=self.organization,
            user=self.owner,
        )

        membership.is_active = False
        membership.save(update_fields=["is_active"])

        self.client.force_login(self.owner)

        response = self.post_grant()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(DatasetAccessGrant.objects.count(), 0)

    def test_inactive_organization_denied(self):
        self.organization.is_active = False
        self.organization.save(update_fields=["is_active"])

        self.client.force_login(self.owner)

        response = self.post_grant()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(DatasetAccessGrant.objects.count(), 0)

    def test_admin_can_issue_grant(self):
        membership = OrganizationMembership.objects.get(
            organization=self.organization,
            user=self.owner,
        )

        membership.role = "admin"
        membership.save(update_fields=["role"])

        self.client.force_login(self.owner)

        response = self.post_grant()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(DatasetAccessGrant.objects.count(), 1)

    def test_analyst_cannot_revoke_grant(self):
        self.client.force_login(self.owner)

        created = self.post_grant()
        self.assertEqual(created.status_code, 201)

        grant_id = created.json()["id"]

        revoke_url = reverse(
            "organizations:datasets:grant-revoke",
            kwargs={
                "organization_id": self.organization.id,
                "dataset_id": self.dataset.id,
                "grant_id": grant_id,
            },
        )

        self.client.force_login(self.analyst)

        response = self.client.post(revoke_url)

        self.assertEqual(response.status_code, 403)

        grant = DatasetAccessGrant.objects.get(id=grant_id)
        self.assertTrue(grant.is_active)

    def test_duplicate_revocation_rejected(self):
        self.client.force_login(self.owner)

        created = self.post_grant()
        self.assertEqual(created.status_code, 201)

        revoke_url = reverse(
            "organizations:datasets:grant-revoke",
            kwargs={
                "organization_id": self.organization.id,
                "dataset_id": self.dataset.id,
                "grant_id": created.json()["id"],
            },
        )

        first = self.client.post(revoke_url)
        second = self.client.post(revoke_url)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 400)

        grant = DatasetAccessGrant.objects.get(
            id=created.json()["id"],
        )
        self.assertFalse(grant.is_active)
    @skipUnless(__import__("django").db.connections["default"].vendor == "sqlite", "SQLite-specific locking test")

    def test_sqlite_lock_returns_retryable_response(self):
        from unittest.mock import patch
        from django.db import OperationalError

        self.client.force_login(self.owner)

        with patch(
            "datasets.grant_views.issue_dataset_access_grant",
            side_effect=OperationalError(
                "database table is locked: datasets_datasetaccessgrant"
            ),
        ):
            response = self.post_grant()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "1")
        self.assertNotIn(
            "datasets_datasetaccessgrant",
            response.content.decode(),
        )
        self.assertEqual(DatasetAccessGrant.objects.count(), 0)
    @skipUnless(__import__("django").db.connections["default"].vendor == "sqlite", "SQLite-specific locking test")

    def test_revocation_sqlite_lock_returns_503(self):
        from unittest.mock import patch
        from django.db import OperationalError

        self.client.force_login(self.owner)

        created = self.post_grant()
        self.assertEqual(created.status_code, 201)

        grant_id = created.json()["id"]

        revoke_url = reverse(
            "organizations:datasets:grant-revoke",
            kwargs={
                "organization_id": self.organization.id,
                "dataset_id": self.dataset.id,
                "grant_id": grant_id,
            },
        )

        with patch(
            "datasets.grant_views.revoke_dataset_access_grant",
            side_effect=OperationalError(
                "database table is locked: datasets_datasetaccessgrant"
            ),
        ):
            response = self.client.post(revoke_url)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "1")
        self.assertNotIn(
            "datasets_datasetaccessgrant",
            response.content.decode(),
        )

        grant = DatasetAccessGrant.objects.get(id=grant_id)
        self.assertTrue(grant.is_active)
        self.assertIsNone(grant.revoked_at)

    def test_unrelated_database_error_is_not_masked(self):
        from unittest.mock import patch
        from django.db import OperationalError

        self.client.force_login(self.owner)

        with patch(
            "datasets.grant_views.issue_dataset_access_grant",
            side_effect=OperationalError(
                "Simulated unrelated database failure"
            ),
        ):
            with self.assertRaises(OperationalError):
                self.post_grant()

        self.assertEqual(DatasetAccessGrant.objects.count(), 0)
