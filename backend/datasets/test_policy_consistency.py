"""Verify consistency between dataset listing and retrieval policies."""

from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import TestCase

from organizations.models import Organization, OrganizationMembership

from .models import CorporateDataset
from .services import get_accessible_dataset, list_accessible_datasets


class DatasetPolicyConsistencyTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="policy_consistency_user",
            password="local-test-password",
        )

        self.organization = Organization.objects.create(
            name="Policy Test Company",
            slug="policy-test-company",
        )

        self.membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role="viewer",
        )

        self.internal = CorporateDataset.objects.create(
            organization=self.organization,
            created_by=self.user,
            name="Internal Information",
            classification="internal",
        )

        self.confidential = CorporateDataset.objects.create(
            organization=self.organization,
            created_by=self.user,
            name="Confidential Information",
            classification="confidential",
        )

        self.restricted = CorporateDataset.objects.create(
            organization=self.organization,
            created_by=self.user,
            name="Restricted Information",
            classification="restricted",
        )

    def test_viewer_list_and_retrieval_agree(self):
        visible = list(
            list_accessible_datasets(
                user=self.user,
                organization=self.organization,
            )
        )

        self.assertEqual(visible, [self.internal])

        self.assertEqual(
            get_accessible_dataset(
                user=self.user,
                organization=self.organization,
                dataset_id=self.internal.id,
            ),
            self.internal,
        )

        for dataset in (self.confidential, self.restricted):
            with self.subTest(dataset=dataset.name):
                with self.assertRaises(Http404):
                    get_accessible_dataset(
                        user=self.user,
                        organization=self.organization,
                        dataset_id=dataset.id,
                    )

    def test_analyst_list_and_retrieval_agree(self):
        self.membership.role = "analyst"
        self.membership.save()

        visible = list_accessible_datasets(
            user=self.user,
            organization=self.organization,
        )

        self.assertEqual(
            set(visible.values_list("id", flat=True)),
            {self.internal.id, self.confidential.id},
        )

        for dataset in (self.internal, self.confidential):
            self.assertEqual(
                get_accessible_dataset(
                    user=self.user,
                    organization=self.organization,
                    dataset_id=dataset.id,
                ),
                dataset,
            )

        with self.assertRaises(Http404):
            get_accessible_dataset(
                user=self.user,
                organization=self.organization,
                dataset_id=self.restricted.id,
            )

    def test_owner_still_cannot_view_restricted(self):
        self.membership.role = "owner"
        self.membership.save()

        visible = list_accessible_datasets(
            user=self.user,
            organization=self.organization,
        )

        self.assertNotIn(self.restricted, visible)

        with self.assertRaises(Http404):
            get_accessible_dataset(
                user=self.user,
                organization=self.organization,
                dataset_id=self.restricted.id,
            )

    def test_inactive_membership_denied_everywhere(self):
        self.membership.is_active = False
        self.membership.save()

        visible = list_accessible_datasets(
            user=self.user,
            organization=self.organization,
        )

        self.assertFalse(visible.exists())

        with self.assertRaises(Http404):
            get_accessible_dataset(
                user=self.user,
                organization=self.organization,
                dataset_id=self.internal.id,
            )
