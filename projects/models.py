from django.db import models
from django.conf import settings

class Project(models.Model):
    """
    n-COS Domain Entity: A collaborative project or initiative.
    Adheres to COS Module Contract:
    1. Community-scoped
    2. Uses DomainActivity for logging
    """
    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_ARCHIVED = "archived"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    community = models.ForeignKey(
        "core.Community",
        on_delete=models.CASCADE,
        related_name="projects"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_projects"
    )
    title = models.CharField(max_length=255)
    description = models.TextField()

    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.community.name})"
