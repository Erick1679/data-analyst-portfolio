from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import ClientEnquiry, DataSource, GeographicIndicator, GeographicPlace


class WorldwideGeographyTests(TestCase):
    def setUp(self):
        self.source = DataSource.objects.create(
            name="Synthetic demonstration", publisher="Local test fixture",
            licence_notes="Synthetic data for tests only",
        )
        self.kenya = GeographicPlace.objects.create(
            code="KE", name="Kenya", place_type="country", data_source=self.source
        )
        self.nairobi_county = GeographicPlace.objects.create(
            code="KE-047", name="Nairobi County", place_type="county",
            parent=self.kenya, data_source=self.source,
        )
        self.nairobi_city = GeographicPlace.objects.create(
            code="KE-NRB-CITY", name="Nairobi", place_type="city",
            parent=self.nairobi_county, data_source=self.source,
        )
        self.us = GeographicPlace.objects.create(
            code="US", name="United States", place_type="country",
            data_source=self.source,
        )
        self.california = GeographicPlace.objects.create(
            code="US-CA", name="California", place_type="state",
            parent=self.us, data_source=self.source,
        )
        GeographicIndicator.objects.create(
            source=self.source, place=self.nairobi_county,
            indicator="Synthetic index", period=date(2026, 1, 1),
            value=Decimal("10.25"),
        )

    def test_country_and_child_navigation(self):
        root = self.client.get(reverse("places-api")).json()["results"]
        self.assertEqual({place["code"] for place in root}, {"KE", "US"})
        ke_children = self.client.get(
            reverse("places-api"), {"parent": "KE"}
        ).json()["results"]
        self.assertEqual(ke_children[0]["code"], "KE-047")
        county_children = self.client.get(
            reverse("places-api"), {"parent": "KE-047"}
        ).json()["results"]
        self.assertEqual(county_children[0]["place_type"], "city")

    def test_unapproved_data_is_hidden(self):
        response = self.client.get(reverse("indicator-api"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)

    def test_approved_data_is_filterable(self):
        self.source.approved_for_publication = True
        self.source.save()
        response = self.client.get(reverse("indicator-api"), {"place": "KE-047"})
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["results"][0]["place_type"], "county")
        response = self.client.get(reverse("indicator-api"), {"place": "US-CA"})
        self.assertEqual(response.json()["count"], 0)

    def test_enquiry_is_private(self):
        ClientEnquiry.objects.create(
            name="Private person", email="private@example.test",
            requirements="Confidential project", place=self.california
        )
        content = self.client.get(reverse("indicator-api")).content
        self.assertNotIn(b"private@example.test", content)

    def test_country_cannot_have_parent(self):
        invalid = GeographicPlace(
            code="GB", name="United Kingdom", place_type="country",
            parent=self.kenya
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_geographic_cycles_rejected(self):
        self.kenya.parent = self.nairobi_city
        with self.assertRaises(ValidationError):
            self.kenya.full_clean()
