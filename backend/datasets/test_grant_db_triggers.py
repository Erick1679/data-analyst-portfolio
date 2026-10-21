"""Database-level tenant integrity tests for access grants."""

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.test import TestCase

from organizations.models import Organization, OrganizationMembership

from .models import CorporateDataset, DatasetAccessGrant


class DatasetGrantTriggerTests(TestCase):

    databases = {"default"}

    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            username="grant_trigger_owner",
            password="local-test-password",
        )
        self.recipient = User.objects.create_user(
            username="grant_trigger_recipient",
            password="local-test-password",
        )

        self.org_a = Organization.objects.create(
            name="Grant Trigger Company A",
            slug="grant-trigger-company-a",
        )
        self.org_b = Organization.objects.create(
            name="Grant Trigger Company B",
            slug="grant-trigger-company-b",
        )

        self.membership_a = OrganizationMembership.objects.create(
            organization=self.org_a,
            user=self.recipient,
            role="analyst",
        )
        self.membership_b = OrganizationMembership.objects.create(
            organization=self.org_b,
            user=self.recipient,
            role="analyst",
        )

        self.dataset = CorporateDataset.objects.create(
            organization=self.org_a,
            created_by=self.owner,
            name="Grant Trigger Restricted Dataset",
            classification="restricted",
        )

    def test_cross_organization_grant_insert_is_blocked(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DatasetAccessGrant.objects.create(
                    dataset=self.dataset,
                    membership=self.membership_b,
                    granted_by=self.owner,
                )

        self.assertEqual(DatasetAccessGrant.objects.count(), 0)

    def test_cross_organization_grant_update_is_blocked(self):
        grant = DatasetAccessGrant.objects.create(
            dataset=self.dataset,
            membership=self.membership_a,
            granted_by=self.owner,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DatasetAccessGrant.objects.filter(pk=grant.pk).update(
                    membership=self.membership_b,
                )

        grant.refresh_from_db()
        self.assertEqual(grant.membership, self.membership_a)

    def test_dataset_organization_reassignment_is_blocked(self):
        DatasetAccessGrant.objects.create(
            dataset=self.dataset,
            membership=self.membership_a,
            granted_by=self.owner,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CorporateDataset.objects.filter(
                    pk=self.dataset.pk
                ).update(organization=self.org_b)

        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.organization, self.org_a)

    def test_membership_organization_reassignment_is_blocked(self):
        DatasetAccessGrant.objects.create(
            dataset=self.dataset,
            membership=self.membership_a,
            granted_by=self.owner,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrganizationMembership.objects.filter(
                    pk=self.membership_a.pk
                ).update(organization=self.org_b)

        self.membership_a.refresh_from_db()
        self.assertEqual(self.membership_a.organization, self.org_a)
