from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase

from organizations.models import Organization, OrganizationMembership
from retail.models import Product
from retail.permissions import (
    can_access_retail_record,
    has_retail_permission,
)


class RetailPermissionTests(TestCase):
    """Verify organization-scoped retail authorization."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.owner = User.objects.create_user(
            username="retail_security_owner",
            password="test-password-not-for-production",
        )
        cls.viewer = User.objects.create_user(
            username="retail_security_viewer",
            password="test-password-not-for-production",
        )
        cls.outsider = User.objects.create_user(
            username="retail_security_outsider",
            password="test-password-not-for-production",
        )

        cls.organization_a = Organization.objects.create(
            name="Retail Security Organization A",
            slug="retail-security-org-a",
        )
        cls.organization_b = Organization.objects.create(
            name="Retail Security Organization B",
            slug="retail-security-org-b",
        )

        OrganizationMembership.objects.create(
            organization=cls.organization_a,
            user=cls.owner,
            role="owner",
        )
        OrganizationMembership.objects.create(
            organization=cls.organization_a,
            user=cls.viewer,
            role="viewer",
        )

        cls.product_a = Product.objects.create(
            organization=cls.organization_a,
            sku="SECURITY-001",
            name="Security Test Product",
            unit_price="100.00",
        )
        cls.product_b = Product.objects.create(
            organization=cls.organization_b,
            sku="SECURITY-001",
            name="Other Organization Product",
            unit_price="100.00",
        )

    def test_unauthenticated_user_denied(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertFalse(
            has_retail_permission(
                AnonymousUser(),
                self.organization_a,
                "view_retail",
            )
        )

    def test_inactive_user_denied(self):
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])

        self.assertFalse(
            has_retail_permission(
                self.owner,
                self.organization_a,
                "view_retail",
            )
        )

    def test_user_without_membership_denied(self):
        self.assertFalse(
            has_retail_permission(
                self.outsider,
                self.organization_a,
                "view_retail",
            )
        )

    def test_inactive_organization_denied(self):
        self.organization_a.is_active = False
        self.organization_a.save(update_fields=["is_active"])

        self.assertFalse(
            has_retail_permission(
                self.owner,
                self.organization_a,
                "view_retail",
            )
        )

    def test_inactive_membership_denied(self):
        OrganizationMembership.objects.filter(
            organization=self.organization_a,
            user=self.owner,
        ).update(is_active=False)

        self.assertFalse(
            has_retail_permission(
                self.owner,
                self.organization_a,
                "view_retail",
            )
        )

    def test_owner_can_manage_products(self):
        self.assertTrue(
            has_retail_permission(
                self.owner,
                self.organization_a,
                "manage_products",
            )
        )

    def test_viewer_cannot_manage_products(self):
        self.assertFalse(
            has_retail_permission(
                self.viewer,
                self.organization_a,
                "manage_products",
            )
        )

    def test_cross_organization_record_access_denied(self):
        self.assertFalse(
            can_access_retail_record(
                self.owner,
                self.product_b,
                "view_retail",
            )
        )

        self.assertTrue(
            can_access_retail_record(
                self.owner,
                self.product_a,
                "view_retail",
            )
        )

    def test_multiple_memberships_are_independent(self):
        OrganizationMembership.objects.create(
            organization=self.organization_b,
            user=self.owner,
            role="viewer",
        )

        self.assertTrue(
            has_retail_permission(
                self.owner,
                self.organization_b,
                "view_retail",
            )
        )

        self.assertFalse(
            has_retail_permission(
                self.owner,
                self.organization_b,
                "manage_products",
            )
        )

        self.assertTrue(
            has_retail_permission(
                self.owner,
                self.organization_a,
                "manage_products",
            )
        )

    def test_record_without_organization_denied(self):
        record = SimpleNamespace(name="Unowned record")

        self.assertFalse(
            can_access_retail_record(
                self.owner,
                record,
                "view_retail",
            )
        )
