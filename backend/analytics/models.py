import re

from django.core.exceptions import ValidationError
from django.db import models


class DataSource(models.Model):
    """Data provenance and usage rights; never assume commercial permission."""
    name = models.CharField(max_length=160)
    publisher = models.CharField(max_length=160)
    source_url = models.URLField(blank=True)
    licence_notes = models.TextField()
    approved_for_publication = models.BooleanField(default=False)
    approved_for_commercial_use = models.BooleanField(default=False)
    last_imported_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class GeographicPlace(models.Model):
    """Country roots with flexible, nested regional and local divisions."""

    COUNTRY = "country"
    TYPES = [
        ("country", "Country or territory"),
        ("state", "State"),
        ("province", "Province"),
        ("region", "Region"),
        ("county", "County"),
        ("district", "District"),
        ("city", "City"),
        ("town", "Town"),
        ("municipality", "Municipality"),
        ("department", "Department"),
        ("prefecture", "Prefecture"),
        ("territory", "Territory"),
        ("other", "Other geographic division"),
    ]
    # Globally unique, externally assignable place key: KE, KE-047, US-CA, ...
    # Non-country codes may be local identifiers, and are not claimed as ISO codes.
    code = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=180)
    place_type = models.CharField(max_length=20, choices=TYPES)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT,
        related_name="children",
    )
    data_source = models.ForeignKey(
        DataSource, null=True, blank=True, on_delete=models.PROTECT,
        help_text="Source of this geographic reference record",
    )

    class Meta:
        ordering = ["name", "code"]
        indexes = [models.Index(fields=["parent", "name"])]

    def clean(self):
        super().clean()
        if self.place_type == self.COUNTRY:
            if self.parent_id is not None:
                raise ValidationError({"parent": "Countries cannot have a parent."})
            if not re.fullmatch(r"[A-Z]{2}", self.code or ""):
                raise ValidationError({"code": "Country codes must be ISO 3166-1 alpha-2 style."})
        elif self.parent_id is None:
            raise ValidationError({"parent": "Subnational areas and cities require a parent."})

        ancestor = self.parent
        visited = set()
        while ancestor is not None:
            if ancestor.pk and (ancestor.pk == self.pk or ancestor.pk in visited):
                raise ValidationError({"parent": "Geographic parent links cannot contain cycles."})
            if ancestor.pk:
                visited.add(ancestor.pk)
            ancestor = ancestor.parent

    @property
    def label_path(self):
        pieces = [self.name]
        ancestor = self.parent
        visited = set()
        while ancestor is not None and ancestor.pk not in visited:
            visited.add(ancestor.pk)
            pieces.append(ancestor.name)
            ancestor = ancestor.parent
        return " / ".join(reversed(pieces))

    def __str__(self):
        return f"{self.name} ({self.code})"



class LocalAuthority(models.Model):
    """A governing body, not an additional geographic place.

    A council's relationship to a GeographicPlace is optional and should
    only be entered after verifying its exact jurisdiction.
    """

    AUTHORITY_TYPES = [
        ("district_council", "District council"),
        ("city_council", "City council"),
        ("town_council", "Town council"),
        ("municipal_council", "Municipal council"),
        ("regional_council", "Regional council"),
        ("other", "Other local authority"),
    ]
    VERIFICATION_STATUSES = [
        ("pending", "Pending verification"),
        ("verified", "Verified against authoritative source"),
    ]

    name = models.CharField(max_length=180)
    country = models.ForeignKey(
        GeographicPlace, on_delete=models.PROTECT,
        related_name="local_authorities",
        help_text="Choose a country or territory, not a district or town.",
    )
    authority_type = models.CharField(
        max_length=24, choices=AUTHORITY_TYPES, default="other",
    )
    jurisdiction = models.ForeignKey(
        GeographicPlace, null=True, blank=True, on_delete=models.PROTECT,
        related_name="linked_local_authorities",
        help_text="Optional. Link only to a geographically verified jurisdiction.",
    )
    source = models.ForeignKey(
        DataSource, on_delete=models.PROTECT,
        related_name="local_authorities",
    )
    verification_status = models.CharField(
        max_length=12, choices=VERIFICATION_STATUSES, default="pending",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["country__name", "name"]
        verbose_name_plural = "Local authorities"
        constraints = [
            models.UniqueConstraint(
                fields=["country", "name"],
                name="unique_local_authority_name_per_country",
            ),
        ]

    def clean(self):
        super().clean()
        if not self.country_id:
            return
        if self.country.place_type != GeographicPlace.COUNTRY:
            raise ValidationError({
                "country": "A local authority must be assigned to a country."
            })
        if not self.jurisdiction_id:
            return
        ancestor = self.jurisdiction
        visited = set()
        if ancestor.pk == self.country_id:
            raise ValidationError({
                "jurisdiction": "Link a verified subnational area, or leave blank."
            })
        while ancestor is not None:
            if ancestor.pk == self.country_id:
                return
            if ancestor.pk in visited:
                break
            visited.add(ancestor.pk)
            ancestor = ancestor.parent
        raise ValidationError({
            "jurisdiction": "The linked area must belong to the selected country."
        })

    def __str__(self):
        return f"{self.name} ({self.country.code})"


class GeographicIndicator(models.Model):
    """A published aggregate statistical observation for any geographic level."""
    source = models.ForeignKey(DataSource, on_delete=models.PROTECT)
    place = models.ForeignKey(
        GeographicPlace, on_delete=models.PROTECT, related_name="indicators"
    )
    indicator = models.CharField(max_length=160)
    period = models.DateField()
    value = models.DecimalField(max_digits=20, decimal_places=4)
    unit = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["-period", "place__name", "indicator"]
        constraints = [models.UniqueConstraint(
            fields=["source", "place", "indicator", "period"],
            name="unique_source_place_indicator_period",
        )]

    def __str__(self):
        return f"{self.place.name}: {self.indicator} ({self.period})"


class ClientEnquiry(models.Model):
    """Private data, administered only by staff; not an SMS subscriber database."""
    STATUSES = [
        ("new", "New"), ("review", "Under review"),
        ("active", "In progress"), ("closed", "Closed"),
    ]
    name = models.CharField(max_length=160)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    place = models.ForeignKey(
        GeographicPlace, null=True, blank=True, on_delete=models.SET_NULL
    )
    requirements = models.TextField()
    consent_to_contact = models.BooleanField(default=False)
    marketing_opt_in = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=STATUSES, default="new")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Project(models.Model):
    STATUSES = [
        ("planned", "Planned"), ("ongoing", "In progress"), ("done", "Completed")
    ]
    title = models.CharField(max_length=180)
    enquiry = models.ForeignKey(
        ClientEnquiry, on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(max_length=12, choices=STATUSES, default="planned")
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.title
