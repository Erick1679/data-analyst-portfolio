from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from organizations.models import Organization
from retail.models import Branch, Product


class RetailModelTests(TestCase):
    """Verify retail model validation and organization boundaries."""

    @classmethod
    def setUpTestData(cls):
        cls.organization_a = Organization.objects.create(
            name="Retail Test Organization A",
            slug="retail-test-organization-a",
        )
        cls.organization_b = Organization.objects.create(
            name="Retail Test Organization B",
            slug="retail-test-organization-b",
        )

    def test_branch_belongs_to_correct_organization(self):
        branch = Branch.objects.create(
            organization=self.organization_a,
            code="MAIN",
            name="Main Branch",
        )

        self.assertEqual(
            branch.organization_id,
            self.organization_a.id,
        )

    def test_branch_code_unique_within_organization(self):
        Branch.objects.create(
            organization=self.organization_a,
            code="MAIN",
            name="First Branch",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Branch.objects.create(
                    organization=self.organization_a,
                    code="MAIN",
                    name="Duplicate Branch",
                )

    def test_different_organizations_can_share_branch_code(self):
        for organization in (
            self.organization_a,
            self.organization_b,
        ):
            Branch.objects.create(
                organization=organization,
                code="MAIN",
                name="Main Branch",
            )

        self.assertEqual(
            Branch.objects.filter(code="MAIN").count(),
            2,
        )

    def test_product_belongs_to_correct_organization(self):
        product = Product.objects.create(
            organization=self.organization_a,
            sku="SKU001",
            name="Sample Product",
            unit_price=Decimal("250.00"),
        )

        self.assertEqual(
            product.organization_id,
            self.organization_a.id,
        )

    def test_product_sku_unique_within_organization(self):
        Product.objects.create(
            organization=self.organization_a,
            sku="SKU001",
            name="First Product",
            unit_price=Decimal("250.00"),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Product.objects.create(
                    organization=self.organization_a,
                    sku="SKU001",
                    name="Duplicate Product",
                    unit_price=Decimal("250.00"),
                )

    def test_different_organizations_can_share_sku(self):
        for organization in (
            self.organization_a,
            self.organization_b,
        ):
            Product.objects.create(
                organization=organization,
                sku="SKU001",
                name="Sample Product",
                unit_price=Decimal("250.00"),
            )

        self.assertEqual(
            Product.objects.filter(sku="SKU001").count(),
            2,
        )

    def test_negative_price_rejected_by_model_validation(self):
        product = Product(
            organization=self.organization_a,
            sku="NEGATIVE",
            name="Invalid Product",
            unit_price=Decimal("-1.00"),
        )

        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_negative_price_rejected_by_database(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Product.objects.create(
                    organization=self.organization_a,
                    sku="NEGATIVE-DB",
                    name="Invalid Product",
                    unit_price=Decimal("-1.00"),
                )
