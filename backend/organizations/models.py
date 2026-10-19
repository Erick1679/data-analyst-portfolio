import uuid

from django.conf import settings
from django.db import models


class Organization(models.Model):
    """A corporate customer of The Brights Analytics."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class OrganizationMembership(models.Model):
    """A user's position and access role within an organization."""

    class AccessRole(models.TextChoices):
        OWNER = "owner", "Organization Owner"
        ADMIN = "admin", "Administrator"
        MANAGER = "manager", "Manager"
        EDITOR = "editor", "Editor"
        ANALYST = "analyst", "Analyst"
        AUDITOR = "auditor", "Auditor"
        VIEWER = "viewer", "Viewer"

    class Position(models.TextChoices):
        OWNER = "owner", "Organization Owner"
        CEO = "ceo", "Chief Executive Officer"
        CFO = "cfo", "Chief Financial Officer"
        COO = "coo", "Chief Operating Officer"
        CTO = "cto", "Chief Technology Officer"
        EXECUTIVE_DIRECTOR = "executive_director", "Executive Director"
        DIRECTOR = "director", "Department Director"
        DEPARTMENT_HEAD = "department_head", "Department Head"
        SENIOR_MANAGER = "senior_manager", "Senior Manager"
        MANAGER = "manager", "Manager"
        SUPERVISOR = "supervisor", "Supervisor"
        SENIOR_ANALYST = "senior_analyst", "Senior Analyst"
        ANALYST = "analyst", "Data or Business Analyst"
        SENIOR_EMPLOYEE = "senior_employee", "Senior Employee"
        EMPLOYEE = "employee", "Employee"
        JUNIOR_EMPLOYEE = "junior_employee", "Junior Employee"
        INTERN = "intern", "Intern or Trainee"
        EXTERNAL_AUDITOR = "external_auditor", "External Auditor"
        OTHER = "other", "Other Position"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=AccessRole.choices,
        default=AccessRole.VIEWER,
    )
    position = models.CharField(
        max_length=30,
        choices=Position.choices,
        default=Position.OTHER,
    )
    department = models.CharField(
        max_length=100,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"],
                name="unique_organization_membership",
            )
        ]

    def __str__(self):
        return (
            f"{self.user_id} - "
            f"{self.organization.name} ({self.role})"
        )
