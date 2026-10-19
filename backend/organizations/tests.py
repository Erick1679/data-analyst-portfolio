from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Organization, OrganizationMembership


class OrganizationModelTests(TestCase):

    def test_create_organization_with_uuid(self):
        org = Organization.objects.create(
            name="Example Corporation",
            slug="example-corporation",
        )
        self.assertIsNotNone(org.id)
        self.assertTrue(org.is_active)

    def test_organization_slug_must_be_unique(self):
        Organization.objects.create(
            name="Example Corporation",
            slug="example",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Organization.objects.create(
                    name="Another Corporation",
                    slug="example",
                )


class OrganizationMembershipTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="testmember",
            password="test-password-for-local-tests",
        )
        self.organization = Organization.objects.create(
            name="Example Corporation",
            slug="example-corporation",
        )

    def test_default_membership_role_is_viewer(self):
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
        )

        self.assertEqual(membership.role, "viewer")
        self.assertEqual(membership.position, "other")
        self.assertTrue(membership.is_active)

    def test_job_position_is_separate_from_access_role(self):
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            position="ceo",
            role="viewer",
        )

        self.assertEqual(membership.position, "ceo")
        self.assertEqual(membership.role, "viewer")

    def test_duplicate_membership_is_rejected(self):
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrganizationMembership.objects.create(
                    organization=self.organization,
                    user=self.user,
                )

    def test_user_can_join_multiple_organizations(self):
        other_organization = Organization.objects.create(
            name="Second Corporation",
            slug="second-corporation",
        )

        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
        )
        OrganizationMembership.objects.create(
            organization=other_organization,
            user=self.user,
        )

        self.assertEqual(
            OrganizationMembership.objects.filter(
                user=self.user
            ).count(),
            2,
        )
