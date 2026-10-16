from django.db import models


class DataSource(models.Model):
    name = models.CharField(max_length=160)
    publisher = models.CharField(max_length=160)
    source_url = models.URLField(blank=True)
    licence_notes = models.TextField()
    approved_for_publication = models.BooleanField(default=False)
    approved_for_commercial_use = models.BooleanField(default=False)
    last_imported_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class CountyIndicator(models.Model):
    """Only aggregate metrics, no person-level records."""
    source = models.ForeignKey(DataSource, on_delete=models.PROTECT)
    county = models.CharField(max_length=100)
    indicator = models.CharField(max_length=160)
    period = models.DateField()
    value = models.DecimalField(max_digits=18, decimal_places=2)
    unit = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["-period", "county", "indicator"]
        constraints = [models.UniqueConstraint(
            fields=["source", "county", "indicator", "period"],
            name="unique_source_county_indicator_period",
        )]

    def __str__(self):
        return f"{self.county}: {self.indicator} ({self.period})"


class ClientEnquiry(models.Model):
    STATUSES = [
        ("new", "New"), ("review", "Under review"),
        ("active", "In progress"), ("closed", "Closed"),
    ]
    name = models.CharField(max_length=160)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    county = models.CharField(max_length=100, blank=True)
    requirements = models.TextField()
    consent_to_contact = models.BooleanField(default=False)
    marketing_opt_in = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=STATUSES, default="new")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Project(models.Model):
    STATUSES = [
        ("planned", "Planned"),
        ("ongoing", "In progress"),
        ("done", "Completed"),
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
