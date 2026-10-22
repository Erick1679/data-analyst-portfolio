"""Model integrity tests for corporate datasets."""

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from organizations.models import Organization
from .models import CorporateDataset


class CorporateDatasetModelTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dataset_test_user",
            password="local-test-password",
        )

        self.company_a = Organization.objects.create(
            name="Company A",
            slug="company-a",
        )

        self.company_b = Organization.objects.create(
            name="Company B",
            slug="company-b",
        )

    def test_dataset_has_organization_owner(self):
        dataset = CorporateDataset.objects.create(
            organization=self.company_a,
            created_by=self.user,
            name="Financial Overview",
        )

        self.assertEqual(
            dataset.organization,
            self.company_a,
        )

    def test_default_classification_is_confidential(self):
        dataset = CorporateDataset.objects.create(
            organization=self.company_a,
            created_by=self.user,
            name="Revenue Report",
        )

        self.assertEqual(
            dataset.classification,
            "confidential",
        )

    def test_default_status_is_draft(self):
        dataset = CorporateDataset.objects.create(
            organization=self.company_a,
            created_by=self.user,
            name="Operational Data",
        )

        self.assertEqual(dataset.status, "draft")

    def test_duplicate_dataset_name_same_organization_rejected(self):
        CorporateDataset.objects.create(
            organization=self.company_a,
            created_by=self.user,
            name="Annual Report",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CorporateDataset.objects.create(
                    organization=self.company_a,
                    created_by=self.user,
                    name="Annual Report",
                )

    def test_same_dataset_name_different_organizations_allowed(self):
        for organization in (self.company_a, self.company_b):
            CorporateDataset.objects.create(
                organization=organization,
                created_by=self.user,
                name="Annual Report",
            )

        self.assertEqual(
            CorporateDataset.objects.filter(
                name="Annual Report"
            ).count(),
            2,
        )

    def test_organization_deletion_is_protected(self):
        from django.db.models import ProtectedError

        CorporateDataset.objects.create(
            organization=self.company_a,
            created_by=self.user,
            name="Protected Dataset",
        )

        with self.assertRaises(ProtectedError):
            self.company_a.delete()
