from unittest import skipUnless
"""HTTP security tests for corporate membership management."""

import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Organization, OrganizationMembership


class MembershipCreationHTTPTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            username="membership_http_owner",
            password="local-test-password",
        )
        self.analyst = User.objects.create_user(
            username="membership_http_analyst",
            password="local-test-password",
        )
        self.recipient = User.objects.create_user(
            username="membership_http_recipient",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Membership HTTP Company",
            slug="membership-http-company",
        )
        self.other_organization = Organization.objects.create(
            name="Other Membership HTTP Company",
            slug="other-membership-http-company",
        )

        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role="owner",
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.analyst,
            role="analyst",
        )

        self.url = reverse(
            "organizations:membership-list",
            kwargs={"organization_id": self.organization.id},
        )

        self.payload = {
            "user_id": self.recipient.pk,
            "role": "viewer",
        }

    def post_membership(self, user=None, url=None):
        client = Client()

        if user is not None:
            client.force_login(user)

        return client.post(
            url or self.url,
            data=json.dumps(self.payload),
            content_type="application/json",
        )

    def test_unauthenticated_creation_rejected(self):
        response = self.post_membership()

        self.assertEqual(response.status_code, 401)

    def test_owner_can_create_membership(self):
        response = self.post_membership(user=self.owner)

        self.assertEqual(response.status_code, 201)

        self.assertTrue(
            OrganizationMembership.objects.filter(
                organization=self.organization,
                user=self.recipient,
                role="viewer",
                is_active=True,
            ).exists()
        )

    def test_analyst_cannot_create_membership(self):
        response = self.post_membership(user=self.analyst)

        self.assertEqual(response.status_code, 403)

    def test_other_organization_hidden(self):
        outside_url = reverse(
            "organizations:membership-list",
            kwargs={
                "organization_id": self.other_organization.id,
            },
        )

        response = self.post_membership(
            user=self.owner,
            url=outside_url,
        )

        self.assertEqual(response.status_code, 404)

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)

        response = client.post(
            self.url,
            data=json.dumps(self.payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

        self.assertFalse(
            OrganizationMembership.objects.filter(
                organization=self.organization,
                user=self.recipient,
            ).exists()
        )

    def test_invalid_json_rejected(self):
        client = Client()
        client.force_login(self.owner)

        response = client.post(
            self.url,
            data="{invalid-json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

        self.assertFalse(
            OrganizationMembership.objects.filter(
                organization=self.organization,
                user=self.recipient,
            ).exists()
        )

    def test_unsupported_content_type_rejected(self):
        client = Client()
        client.force_login(self.owner)

        response = client.post(
            self.url,
            data="user_id=123&role=viewer",
            content_type="text/plain",
        )

        self.assertEqual(response.status_code, 415)

    def test_missing_required_role_rejected(self):
        client = Client()
        client.force_login(self.owner)

        response = client.post(
            self.url,
            data=json.dumps({"user_id": self.recipient.pk}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_invalid_user_id_rejected(self):
        client = Client()
        client.force_login(self.owner)

        response = client.post(
            self.url,
            data=json.dumps({
                "user_id": True,
                "role": "viewer",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_duplicate_membership_rejected(self):
        first_response = self.post_membership(user=self.owner)

        self.assertEqual(first_response.status_code, 201)

        second_response = self.post_membership(user=self.owner)

        self.assertEqual(second_response.status_code, 400)

        self.assertEqual(
            OrganizationMembership.objects.filter(
                organization=self.organization,
                user=self.recipient,
            ).count(),
            1,
        )

    def test_invalid_role_rejected(self):
        client = Client()
        client.force_login(self.owner)

        response = client.post(
            self.url,
            data=json.dumps({
                "user_id": self.recipient.pk,
                "role": "superuser",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

        self.assertFalse(
            OrganizationMembership.objects.filter(
                organization=self.organization,
                user=self.recipient,
            ).exists()
        )

    def test_inactive_recipient_not_found(self):
        self.recipient.is_active = False
        self.recipient.save(update_fields=["is_active"])

        response = self.post_membership(user=self.owner)

        self.assertEqual(response.status_code, 404)

        self.assertFalse(
            OrganizationMembership.objects.filter(
                organization=self.organization,
                user=self.recipient,
            ).exists()
        )

    def test_oversized_request_rejected(self):
        client = Client()
        client.force_login(self.owner)

        response = client.post(
            self.url,
            data=json.dumps({
                "user_id": self.recipient.pk,
                "role": "viewer",
                "padding": "x" * 17000,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 413)

        self.assertFalse(
            OrganizationMembership.objects.filter(
                organization=self.organization,
                user=self.recipient,
            ).exists()
        )
    @skipUnless(__import__("django").db.connections["default"].vendor == "sqlite", "SQLite-specific locking test")

    def test_sqlite_lock_returns_retryable_503(self):
        from unittest.mock import patch
        from django.db import OperationalError

        with patch(
            "organizations.membership_views.create_organization_membership",
            side_effect=OperationalError(
                "database table is locked: organizations_organizationmembership"
            ),
        ):
            response = self.post_membership(user=self.owner)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "1")
        self.assertNotIn(
            "organizations_organizationmembership",
            response.content.decode(),
        )

    def test_unrelated_database_error_is_not_hidden(self):
        from unittest.mock import patch
        from django.db import OperationalError

        with patch(
            "organizations.membership_views.create_organization_membership",
            side_effect=OperationalError("unexpected database failure"),
        ):
            with self.assertRaises(OperationalError):
                self.post_membership(user=self.owner)


class MembershipRoleChangeHTTPTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            username="role_http_owner",
            password="local-test-password",
        )
        self.analyst = User.objects.create_user(
            username="role_http_analyst",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Role Change HTTP Company",
            slug="role-change-http-company",
        )
        self.other_organization = Organization.objects.create(
            name="Outside Role HTTP Company",
            slug="outside-role-http-company",
        )

        self.owner_membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role="owner",
        )
        self.analyst_membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.analyst,
            role="analyst",
        )

        self.url = reverse(
            "organizations:membership-role-change",
            kwargs={
                "organization_id": self.organization.id,
                "membership_id": self.analyst_membership.id,
            },
        )

    def post_role_change(self, user=None, url=None, role="editor"):
        client = Client()

        if user is not None:
            client.force_login(user)

        return client.post(
            url or self.url,
            data=json.dumps({"role": role}),
            content_type="application/json",
        )

    def test_owner_can_change_member_role(self):
        response = self.post_role_change(user=self.owner)

        self.assertEqual(response.status_code, 200)

        self.analyst_membership.refresh_from_db()
        self.assertEqual(self.analyst_membership.role, "editor")

    def test_unauthenticated_role_change_rejected(self):
        response = self.post_role_change()

        self.assertEqual(response.status_code, 401)

    def test_analyst_cannot_change_roles(self):
        response = self.post_role_change(user=self.analyst)

        self.assertEqual(response.status_code, 403)

        self.analyst_membership.refresh_from_db()
        self.assertEqual(self.analyst_membership.role, "analyst")

    def test_cross_organization_role_change_hidden(self):
        outside_membership = OrganizationMembership.objects.create(
            organization=self.other_organization,
            user=self.analyst,
            role="viewer",
        )

        outside_url = reverse(
            "organizations:membership-role-change",
            kwargs={
                "organization_id": self.organization.id,
                "membership_id": outside_membership.id,
            },
        )

        response = self.post_role_change(
            user=self.owner,
            url=outside_url,
        )

        self.assertEqual(response.status_code, 404)

        outside_membership.refresh_from_db()
        self.assertEqual(outside_membership.role, "viewer")

    def test_last_active_owner_cannot_be_demoted(self):
        owner_url = reverse(
            "organizations:membership-role-change",
            kwargs={
                "organization_id": self.organization.id,
                "membership_id": self.owner_membership.id,
            },
        )

        response = self.post_role_change(
            user=self.owner,
            url=owner_url,
            role="admin",
        )

        self.assertEqual(response.status_code, 400)

        self.owner_membership.refresh_from_db()
        self.assertEqual(self.owner_membership.role, "owner")

    def test_role_change_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)

        response = client.post(
            self.url,
            data=json.dumps({"role": "editor"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

        self.analyst_membership.refresh_from_db()
        self.assertEqual(self.analyst_membership.role, "analyst")

    def test_invalid_role_change_rejected(self):
        response = self.post_role_change(
            user=self.owner,
            role="superuser",
        )

        self.assertEqual(response.status_code, 400)

        self.analyst_membership.refresh_from_db()
        self.assertEqual(self.analyst_membership.role, "analyst")

    def test_oversized_role_change_rejected(self):
        client = Client()
        client.force_login(self.owner)

        response = client.post(
            self.url,
            data=json.dumps({
                "role": "editor",
                "padding": "x" * 17000,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 413)

        self.analyst_membership.refresh_from_db()
        self.assertEqual(self.analyst_membership.role, "analyst")
    @skipUnless(__import__("django").db.connections["default"].vendor == "sqlite", "SQLite-specific locking test")

    def test_role_change_sqlite_lock_returns_503(self):
        from unittest.mock import patch
        from django.db import OperationalError

        with patch(
            "organizations.membership_views.change_organization_membership_role",
            side_effect=OperationalError(
                "database table is locked: organizations_organizationmembership"
            ),
        ):
            response = self.post_role_change(user=self.owner)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "1")
        self.assertNotIn(
            "organizations_organizationmembership",
            response.content.decode(),
        )

    def test_role_change_unrelated_database_error_not_hidden(self):
        from unittest.mock import patch
        from django.db import OperationalError

        with patch(
            "organizations.membership_views.change_organization_membership_role",
            side_effect=OperationalError("unexpected database failure"),
        ):
            with self.assertRaises(OperationalError):
                self.post_role_change(user=self.owner)


class MembershipDeactivationHTTPTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            username="deactivation_http_owner",
            password="local-test-password",
        )
        self.analyst = User.objects.create_user(
            username="deactivation_http_analyst",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Deactivation HTTP Company",
            slug="deactivation-http-company",
        )
        self.other_organization = Organization.objects.create(
            name="Outside Deactivation HTTP Company",
            slug="outside-deactivation-http-company",
        )

        self.owner_membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role="owner",
        )
        self.analyst_membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.analyst,
            role="analyst",
        )

        self.url = reverse(
            "organizations:membership-deactivate",
            kwargs={
                "organization_id": self.organization.id,
                "membership_id": self.analyst_membership.id,
            },
        )

    def post_deactivate(self, user=None, url=None):
        client = Client()

        if user is not None:
            client.force_login(user)

        return client.post(
            url or self.url,
            data=json.dumps({}),
            content_type="application/json",
        )

    def test_owner_can_deactivate_analyst(self):
        response = self.post_deactivate(user=self.owner)

        self.assertEqual(response.status_code, 200)

        self.analyst_membership.refresh_from_db()
        self.assertFalse(self.analyst_membership.is_active)

    def test_unauthenticated_deactivation_rejected(self):
        response = self.post_deactivate()

        self.assertEqual(response.status_code, 401)

    def test_analyst_cannot_deactivate_membership(self):
        response = self.post_deactivate(user=self.analyst)

        self.assertEqual(response.status_code, 403)

        self.analyst_membership.refresh_from_db()
        self.assertTrue(self.analyst_membership.is_active)

    def test_cross_organization_deactivation_hidden(self):
        outside = OrganizationMembership.objects.create(
            organization=self.other_organization,
            user=self.analyst,
            role="viewer",
        )

        outside_url = reverse(
            "organizations:membership-deactivate",
            kwargs={
                "organization_id": self.organization.id,
                "membership_id": outside.id,
            },
        )

        response = self.post_deactivate(
            user=self.owner,
            url=outside_url,
        )

        self.assertEqual(response.status_code, 404)

        outside.refresh_from_db()
        self.assertTrue(outside.is_active)

    def test_last_active_owner_cannot_be_deactivated(self):
        owner_url = reverse(
            "organizations:membership-deactivate",
            kwargs={
                "organization_id": self.organization.id,
                "membership_id": self.owner_membership.id,
            },
        )

        response = self.post_deactivate(
            user=self.owner,
            url=owner_url,
        )

        self.assertEqual(response.status_code, 400)

        self.owner_membership.refresh_from_db()
        self.assertTrue(self.owner_membership.is_active)

    def test_deactivation_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)

        response = client.post(
            self.url,
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

        self.analyst_membership.refresh_from_db()
        self.assertTrue(self.analyst_membership.is_active)

    def test_repeated_deactivation_rejected(self):
        first_response = self.post_deactivate(user=self.owner)
        self.assertEqual(first_response.status_code, 200)

        second_response = self.post_deactivate(user=self.owner)
        self.assertEqual(second_response.status_code, 400)

        self.analyst_membership.refresh_from_db()
        self.assertFalse(self.analyst_membership.is_active)

    def test_deactivation_nonempty_payload_rejected(self):
        client = Client()
        client.force_login(self.owner)

        response = client.post(
            self.url,
            data=json.dumps({"unexpected": True}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

        self.analyst_membership.refresh_from_db()
        self.assertTrue(self.analyst_membership.is_active)
    @skipUnless(__import__("django").db.connections["default"].vendor == "sqlite", "SQLite-specific locking test")

    def test_deactivation_sqlite_lock_returns_503(self):
        from unittest.mock import patch
        from django.db import OperationalError

        with patch(
            "organizations.membership_views.deactivate_organization_membership",
            side_effect=OperationalError(
                "database table is locked: organizations_organizationmembership"
            ),
        ):
            response = self.post_deactivate(user=self.owner)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "1")
        self.assertNotIn(
            "organizations_organizationmembership",
            response.content.decode(),
        )

    def test_deactivation_unrelated_database_error_not_hidden(self):
        from unittest.mock import patch
        from django.db import OperationalError

        with patch(
            "organizations.membership_views.deactivate_organization_membership",
            side_effect=OperationalError("unexpected database failure"),
        ):
            with self.assertRaises(OperationalError):
                self.post_deactivate(user=self.owner)
