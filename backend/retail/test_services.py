from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from organizations.models import Organization, OrganizationMembership
from retail.models import Branch, Product
from retail.services import (
    get_organization_branches,
    get_organization_products,
)


class RetailServiceTests(TestCase):
    """Verify organization-scoped retail read services."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.owner = User.objects.create_user(
            username="retail_service_owner",
        )
        cls.outsider = User.objects.create_user(
            username="retail_service_outsider",
        )

        cls.organization_a = Organization.objects.create(
            name="Service Test Organization A",
            slug="retail-service-org-a",
        )
        cls.organization_b = Organization.objects.create(
            name="Service Test Organization B",
            slug="retail-service-org-b",
        )

        OrganizationMembership.objects.create(
            organization=cls.organization_a,
            user=cls.owner,
            role="owner",
        )

        cls.product_a = Product.objects.create(
            organization=cls.organization_a,
            sku="SERVICE-001",
            name="Product A",
            unit_price=Decimal("100.00"),
        )
        cls.product_b = Product.objects.create(
            organization=cls.organization_b,
            sku="SERVICE-001",
            name="Product B",
            unit_price=Decimal("200.00"),
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

    def test_authorized_product_query_returns_own_records(self):
        products = list(
            get_organization_products(
                self.owner,
                self.organization_a,
            )
        )

        self.assertEqual(products, [self.product_a])

    def test_authorized_branch_query_returns_own_records(self):
        branches = list(
            get_organization_branches(
                self.owner,
                self.organization_a,
            )
        )

        self.assertEqual(branches, [self.branch_a])

    def test_product_query_excludes_other_organization(self):
        products = get_organization_products(
            self.owner,
            self.organization_a,
        )

        self.assertFalse(
            products.filter(pk=self.product_b.pk).exists()
        )

    def test_branch_query_excludes_other_organization(self):
        branches = get_organization_branches(
            self.owner,
            self.organization_a,
        )

        self.assertFalse(
            branches.filter(pk=self.branch_b.pk).exists()
        )

    def test_owner_cannot_query_unjoined_organization(self):
        with self.assertRaises(PermissionDenied):
            get_organization_products(
                self.owner,
                self.organization_b,
            )

        with self.assertRaises(PermissionDenied):
            get_organization_branches(
                self.owner,
                self.organization_b,
            )

    def test_outsider_denied_product_access(self):
        with self.assertRaises(PermissionDenied):
            get_organization_products(
                self.outsider,
                self.organization_a,
            )

    def test_outsider_denied_branch_access(self):
        with self.assertRaises(PermissionDenied):
            get_organization_branches(
                self.outsider,
                self.organization_a,
            )

    def test_inactive_membership_denied(self):
        OrganizationMembership.objects.filter(
            user=self.owner,
            organization=self.organization_a,
        ).update(is_active=False)

        with self.assertRaises(PermissionDenied):
            get_organization_products(
                self.owner,
                self.organization_a,
            )

        with self.assertRaises(PermissionDenied):
            get_organization_branches(
                self.owner,
                self.organization_a,
            )

    def test_inactive_organization_denied(self):
        self.organization_a.is_active = False
        self.organization_a.save(update_fields=["is_active"])

        with self.assertRaises(PermissionDenied):
            get_organization_products(
                self.owner,
                self.organization_a,
            )

    def test_multiple_organization_memberships_stay_scoped(self):
        OrganizationMembership.objects.create(
            organization=self.organization_b,
            user=self.owner,
            role="viewer",
        )

        products_a = list(
            get_organization_products(
                self.owner,
                self.organization_a,
            )
        )

        products_b = list(
            get_organization_products(
                self.owner,
                self.organization_b,
            )
        )

        self.assertEqual(products_a, [self.product_a])
        self.assertEqual(products_b, [self.product_b])
