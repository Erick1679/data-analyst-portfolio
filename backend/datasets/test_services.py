"""Security tests for tenant-scoped dataset services."""

import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.test import TestCase

from organizations.models import Organization, OrganizationMembership

from .models import CorporateDataset
from .services import (
    create_dataset,
    get_accessible_dataset,
    list_accessible_datasets,
)


class DatasetServiceTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="service_test_user",
            password="local-test-password",
        )

        self.company_a = Organization.objects.create(
            name="Company A",
            slug="service-company-a",
        )
        self.company_b = Organization.objects.create(
            name="Company B",
            slug="service-company-b",
        )

        self.membership = OrganizationMembership.objects.create(
            organization=self.company_a,
            user=self.user,
            role="analyst",
        )

        self.dataset_a = CorporateDataset.objects.create(
            organization=self.company_a,
            created_by=self.user,
            name="Company A Finance",
            classification="confidential",
        )

        self.dataset_b = CorporateDataset.objects.create(
            organization=self.company_b,
            created_by=self.user,
            name="Company B Finance",
            classification="confidential",
        )

    def test_authorized_dataset_creation(self):
        dataset = create_dataset(
            user=self.user,
            organization=self.company_a,
            name="New Financial Report",
        )
        self.assertEqual(dataset.organization, self.company_a)
        self.assertEqual(dataset.created_by, self.user)

    def test_cross_organization_creation_denied(self):
        with self.assertRaises(PermissionDenied):
            create_dataset(
                user=self.user,
                organization=self.company_b,
                name="Unauthorized Report",
            )

    def test_viewer_cannot_create_dataset(self):
        self.membership.role = "viewer"
        self.membership.save()

        with self.assertRaises(PermissionDenied):
            create_dataset(
                user=self.user,
                organization=self.company_a,
                name="Viewer Report",
            )

    def test_list_contains_only_authorized_tenant(self):
        datasets = list_accessible_datasets(
            user=self.user,
            organization=self.company_a,
        )
        self.assertIn(self.dataset_a, datasets)
        self.assertNotIn(self.dataset_b, datasets)

    def test_cross_organization_list_is_empty(self):
        datasets = list_accessible_datasets(
            user=self.user,
            organization=self.company_b,
        )
        self.assertEqual(datasets.count(), 0)

    def test_cross_organization_retrieval_denied(self):
        with self.assertRaises(Http404):
            get_accessible_dataset(
                user=self.user,
                organization=self.company_a,
                dataset_id=self.dataset_b.id,
            )

    def test_authorized_retrieval(self):
        dataset = get_accessible_dataset(
            user=self.user,
            organization=self.company_a,
            dataset_id=self.dataset_a.id,
        )
        self.assertEqual(dataset.id, self.dataset_a.id)

    def test_restricted_dataset_hidden_from_listing(self):
        self.dataset_a.classification = "restricted"
        self.dataset_a.save()

        datasets = list_accessible_datasets(
            user=self.user,
            organization=self.company_a,
        )
        self.assertNotIn(self.dataset_a, datasets)

    def test_inactive_membership_cannot_list(self):
        self.membership.is_active = False
        self.membership.save()

        datasets = list_accessible_datasets(
            user=self.user,
            organization=self.company_a,
        )
        self.assertEqual(datasets.count(), 0)

    def test_invalid_dataset_name_rejected(self):
        with self.assertRaises(ValidationError):
            create_dataset(
                user=self.user,
                organization=self.company_a,
                name="",
            )

    def test_unknown_dataset_returns_404(self):
        with self.assertRaises(Http404):
            get_accessible_dataset(
                user=self.user,
                organization=self.company_a,
                dataset_id=uuid.uuid4(),
            )

    def test_viewer_cannot_retrieve_confidential_dataset(self):
        self.membership.role = "viewer"
        self.membership.save()

        with self.assertRaises(Http404):
            get_accessible_dataset(
                user=self.user,
                organization=self.company_a,
                dataset_id=self.dataset_a.id,
            )
