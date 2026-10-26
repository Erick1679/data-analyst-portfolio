"""HTTP security tests for Brights Retail Intelligence."""

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from organizations.models import Organization, OrganizationMembership
from retail.models import Branch, Product


@override_settings(ROOT_URLCONF="retail.test_urls")
class RetailAPITests(TestCase):
    """Verify authenticated organization-scoped retail endpoints."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.owner = User.objects.create_user(
            username="retail_api_owner",
        )
        cls.outsider = User.objects.create_user(
            username="retail_api_outsider",
        )

        cls.organization_a = Organization.objects.create(
            name="API Test Organization A",
            slug="retail-api-org-a",
        )
        cls.organization_b = Organization.objects.create(
            name="API Test Organization B",
            slug="retail-api-org-b",
        )

        OrganizationMembership.objects.create(
            organization=cls.organization_a,
            user=cls.owner,
            role="owner",
        )

        cls.product_a = Product.objects.create(
            organization=cls.organization_a,
            sku="API-001",
            name="Product A",
            unit_price=Decimal("120.50"),
        )
        cls.product_b = Product.objects.create(
            organization=cls.organization_b,
            sku="API-002",
            name="Product B",
            unit_price=Decimal("250.00"),
        )

        cls.branch_a = Branch.objects.create(
            organization=cls.organization_a,
            code="MAIN",
            name="Branch A",
        )
        cls.branch_b = Branch.objects.create(
            organization=cls.organization_b,
            code="MAIN",
            name="Branch B",
        )

    def product_url(self, organization):
        return reverse(
            "test-retail-products",
            kwargs={"organization_id": organization.id},
        )

    def branch_url(self, organization):
        return reverse(
            "test-retail-branches",
            kwargs={"organization_id": organization.id},
        )

    def test_unauthenticated_product_request_denied(self):
        response = self.client.get(
            self.product_url(self.organization_a)
        )
        self.assertNotEqual(response.status_code, 200)
        self.assertEqual(response.status_code, 401)

    def test_unauthenticated_branch_request_denied(self):
        response = self.client.get(
            self.branch_url(self.organization_a)
        )
        self.assertNotEqual(response.status_code, 200)
        self.assertEqual(response.status_code, 401)

    def test_authorized_product_request_succeeds(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.product_url(self.organization_a)
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

    def test_authorized_branch_request_succeeds(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.branch_url(self.organization_a)
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

    def test_products_exclude_other_organization(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.product_url(self.organization_a)
        )

        identifiers = {
            item["id"]
            for item in response.json()["results"]
        }

        self.assertIn(str(self.product_a.id), identifiers)
        self.assertNotIn(str(self.product_b.id), identifiers)

    def test_branches_exclude_other_organization(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.branch_url(self.organization_a)
        )

        identifiers = {
            item["id"]
            for item in response.json()["results"]
        }

        self.assertIn(str(self.branch_a.id), identifiers)
        self.assertNotIn(str(self.branch_b.id), identifiers)

    def test_cross_organization_requests_denied(self):
        self.client.force_login(self.owner)

        for url in (
            self.product_url(self.organization_b),
            self.branch_url(self.organization_b),
        ):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)

    def test_inactive_user_denied(self):
        self.client.force_login(self.owner)

        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])

        response = self.client.get(
            self.product_url(self.organization_a)
        )

        self.assertNotEqual(response.status_code, 200)

    def test_post_requests_are_rejected(self):
        self.client.force_login(self.owner)

        for url in (
            self.product_url(self.organization_a),
            self.branch_url(self.organization_a),
        ):
            response = self.client.post(url)
            self.assertEqual(response.status_code, 405)

    def test_product_serialization_and_organization_id(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.product_url(self.organization_a)
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(
            data["organization_id"],
            str(self.organization_a.id),
        )
        self.assertEqual(
            data["results"][0]["unit_price"],
            "120.50",
        )
        self.assertEqual(
            data["results"][0]["currency"],
            "KES",
        )

    def test_inactive_membership_denied_for_both_endpoints(self):
        self.client.force_login(self.owner)

        OrganizationMembership.objects.filter(
            organization=self.organization_a,
            user=self.owner,
        ).update(is_active=False)

        for url in (
            self.product_url(self.organization_a),
            self.branch_url(self.organization_a),
        ):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)

    def test_inactive_organization_denied_for_both_endpoints(self):
        self.client.force_login(self.owner)

        self.organization_a.is_active = False
        self.organization_a.save(update_fields=["is_active"])

        for url in (
            self.product_url(self.organization_a),
            self.branch_url(self.organization_a),
        ):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)

    def test_nonexistent_organization_returns_404(self):
        self.client.force_login(self.owner)

        missing_id = uuid.uuid4()

        for name in (
            "test-retail-products",
            "test-retail-branches",
        ):
            url = reverse(
                name,
                kwargs={"organization_id": missing_id},
            )

            response = self.client.get(url)
            self.assertEqual(response.status_code, 404)

    def test_outsider_denied_for_both_endpoints(self):
        self.client.force_login(self.outsider)

        for url in (
            self.product_url(self.organization_a),
            self.branch_url(self.organization_a),
        ):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)

    def test_viewer_role_allows_read_only_access(self):
        OrganizationMembership.objects.create(
            organization=self.organization_a,
            user=self.outsider,
            role="viewer",
        )

        self.client.force_login(self.outsider)

        for url in (
            self.product_url(self.organization_a),
            self.branch_url(self.organization_a),
        ):
            self.assertEqual(
                self.client.get(url).status_code,
                200,
            )
            self.assertEqual(
                self.client.post(url).status_code,
                405,
            )

    def test_multiple_memberships_remain_organization_scoped(self):
        OrganizationMembership.objects.create(
            organization=self.organization_b,
            user=self.owner,
            role="viewer",
        )

        self.client.force_login(self.owner)

        for organization, expected_product in (
            (self.organization_a, self.product_a),
            (self.organization_b, self.product_b),
        ):
            response = self.client.get(
                self.product_url(organization)
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                [item["id"] for item in response.json()["results"]],
                [str(expected_product.id)],
            )
