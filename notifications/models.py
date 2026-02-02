# notifications/models.py
from django.db import models

# Create your models here.
from django.db import models
from django.conf import settings


class Notification(models.Model):
    TYPE_EVENT_ANNOUNCEMENT = "event_announcement"
    TYPE_CERTIFICATE_ISSUED = "certificate_issued"
    TYPE_SYSTEM = "system"

    TYPE_CHOICES = [
        (TYPE_EVENT_ANNOUNCEMENT, "Event Announcement"),
        (TYPE_CERTIFICATE_ISSUED, "Certificate Issued"),
        (TYPE_SYSTEM, "System"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(max_length=64, choices=TYPE_CHOICES)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # Optional linking to event
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"], name="notif_user_read_idx"),
            models.Index(fields=["type"], name="notif_type_idx"),
        ]

    def __str__(self):
        return f"{self.user} - {self.type} - {self.title}"
