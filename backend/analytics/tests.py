from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from .models import DataSource, CountyIndicator, ClientEnquiry


class PrivacyTests(TestCase):
    def setUp(self):
        self.source = DataSource.objects.create(
            name="Synthetic test", publisher="Test fixture",
            licence_notes="Synthetic data for tests only"
        )
        CountyIndicator.objects.create(
            source=self.source, county="Nairobi", indicator="Synthetic index",
            period=date(2026, 1, 1), value=Decimal("10.00")
        )

    def test_unapproved_data_cannot_be_seen(self):
        response = self.client.get(reverse("indicator-api"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)

    def test_approved_data_can_be_seen(self):
        self.source.approved_for_publication = True
        self.source.save()
        response = self.client.get(reverse("indicator-api"))
        self.assertEqual(response.json()["count"], 1)

    def test_private_contact_details_not_published(self):
        ClientEnquiry.objects.create(
            name="Private client", email="confidential@example.test",
            requirements="Private project"
        )
        response = self.client.get(reverse("indicator-api"))
        self.assertNotIn(b"confidential@example.test", response.content)
