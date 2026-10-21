"""Tenant-integrity tests for dataset access grants."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from organizations.models import Organization, OrganizationMembership

from .models import CorporateDataset, DatasetAccessGrant


class DatasetGrantIntegrityTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            username="grant_integrity_owner",
            password="local-test-password",
        )

        self.recipient = User.objects.create_user(
            username="grant_integrity_recipient",
            password="local-test-password",
        )

        self.organization_a = Organization.objects.create(
            name="Integrity Company A",
            slug="integrity-company-a",
        )

        self.organization_b = Organization.objects.create(
            name="Integrity Company B",
            slug="integrity-company-b",
        )

        self.membership_a = OrganizationMembership.objects.create(
            organization=self.organization_a,
            user=self.recipient,
            role="analyst",
        )

        self.membership_b = OrganizationMembership.objects.create(
            organization=self.organization_b,
            user=self.recipient,
            role="analyst",
        )

        self.dataset = CorporateDataset.objects.create(
            organization=self.organization_a,
            created_by=self.owner,
            name="Integrity Restricted Dataset",
            classification="restricted",
        )

    def test_same_organization_grant_passes_validation(self):
        grant = DatasetAccessGrant(
            dataset=self.dataset,
            membership=self.membership_a,
            granted_by=self.owner,
        )

        grant.full_clean()

    def test_cross_organization_grant_fails_validation(self):
        grant = DatasetAccessGrant(
            dataset=self.dataset,
            membership=self.membership_b,
            granted_by=self.owner,
        )

        with self.assertRaises(ValidationError):
            grant.full_clean()

        self.assertFalse(
            DatasetAccessGrant.objects.filter(
                dataset=self.dataset,
                membership=self.membership_b,
            ).exists()
        )
