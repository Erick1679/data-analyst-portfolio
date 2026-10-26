"""Integration tests using the real Django retail API routes."""

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from organizations.models import Organization, OrganizationMembership
from retail.models import Branch, Product


class RetailMainURLTests(TestCase):
    """Verify retail API security through the main URL configuration."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.owner = User.objects.create_user(
            username="retail_main_url_owner",
        )
        cls.outsider = User.objects.create_user(
            username="retail_main_url_outsider",
        )

        cls.org_a = Organization.objects.create(
            name="Main URL Retail A",
            slug="main-url-retail-a",
        )
        cls.org_b = Organization.objects.create(
            name="Main URL Retail B",
            slug="main-url-retail-b",
        )

        OrganizationMembership.objects.create(
            organization=cls.org_a,
            user=cls.owner,
            role="owner",
        )

        cls.product_a = Product.objects.create(
            organization=cls.org_a,
            sku="MAIN-A",
            name="Product A",
            unit_price=Decimal("125.50"),
        )
        cls.product_b = Product.objects.create(
            organization=cls.org_b,
            sku="MAIN-B",
            name="Product B",
            unit_price=Decimal("225.50"),
        )

        cls.branch_a = Branch.objects.create(
            organization=cls.org_a,
            code="MAIN",
            name="Branch A",
        )
        cls.branch_b = Branch.objects.create(
            organization=cls.org_b,
            code="MAIN",
            name="Branch B",
        )

    def url(self, name, organization):
        return reverse(
            f"organizations:retail:{name}",
            kwargs={"organization_id": organization.id},
        )

    def test_product_route_resolves_correctly(self):
        url = self.url("product-list", self.org_a)

        self.assertEqual(
            url,
            f"/corporate/{self.org_a.id}/retail/products/",
        )

    def test_branch_route_resolves_correctly(self):
        url = self.url("branch-list", self.org_a)

        self.assertEqual(
            url,
            f"/corporate/{self.org_a.id}/retail/branches/",
        )

    def test_anonymous_requests_return_json_401(self):
        for name in ("product-list", "branch-list"):
            response = self.client.get(self.url(name, self.org_a))

            self.assertEqual(response.status_code, 401)
            self.assertEqual(
                response["Content-Type"],
                "application/json",
            )
            self.assertIn("error", response.json())

    def test_authorized_requests_return_own_data(self):
        self.client.force_login(self.owner)

        for name, expected_id in (
            ("product-list", self.product_a.id),
            ("branch-list", self.branch_a.id),
        ):
            response = self.client.get(self.url(name, self.org_a))

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["count"], 1)
            self.assertEqual(
                response.json()["results"][0]["id"],
                str(expected_id),
            )

    def test_other_organization_is_denied(self):
        self.client.force_login(self.owner)

        for name in ("product-list", "branch-list"):
            response = self.client.get(self.url(name, self.org_b))
            self.assertEqual(response.status_code, 403)

    def test_outsider_is_denied(self):
        self.client.force_login(self.outsider)

        for name in ("product-list", "branch-list"):
            response = self.client.get(self.url(name, self.org_a))
            self.assertEqual(response.status_code, 403)

    def test_inactive_membership_is_denied(self):
        OrganizationMembership.objects.filter(
            organization=self.org_a,
            user=self.owner,
        ).update(is_active=False)

        self.client.force_login(self.owner)

        for name in ("product-list", "branch-list"):
            response = self.client.get(self.url(name, self.org_a))
            self.assertEqual(response.status_code, 403)

    def test_post_is_not_allowed(self):
        self.client.force_login(self.owner)

        for name in ("product-list", "branch-list"):
            response = self.client.post(self.url(name, self.org_a))
            self.assertEqual(response.status_code, 405)

    def test_missing_organization_returns_404(self):
        self.client.force_login(self.owner)
        missing_id = uuid.uuid4()

        for name in ("product-list", "branch-list"):
            response = self.client.get(
                reverse(
                    f"organizations:retail:{name}",
                    kwargs={"organization_id": missing_id},
                )
            )
            self.assertEqual(response.status_code, 404)
