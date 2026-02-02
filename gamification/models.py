from django.db import models
from django.conf import settings

class ReputationLog(models.Model):
    """
    Immutable audit trail of reputation points earned or lost.
    Linked to DomainActivity for traceability ("Why did I get points?").
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reputation_logs",
    )
    community = models.ForeignKey(
        "core.Community",
        on_delete=models.CASCADE,
        related_name="reputation_logs",
    )

    amount = models.IntegerField(help_text="Positive or negative point value")
    reason = models.CharField(max_length=64, help_text="e.g. event.attended")

    # Traceability
    activity = models.ForeignKey(
        "core.DomainActivity",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reputation_impacts",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "community", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user} ({self.amount}) in {self.community}: {self.reason}"


class UserCommunityStats(models.Model):
    """
    Denormalized current stats for a user in a specific community.
    Used for fast UI rendering (Badges, Leaderboards).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_stats",
    )
    community = models.ForeignKey(
        "core.Community",
        on_delete=models.CASCADE,
        related_name="member_stats",
    )

    total_xp = models.IntegerField(default=0)
    current_level = models.IntegerField(default=1)

    # Gamification extras
    # Gamification extras
    # DEPRECATED: Event-specific counters. Use 'stats' JSON below.
    events_attended = models.PositiveIntegerField(default=0)
    events_hosted = models.PositiveIntegerField(default=0)

    # 🔹 Generic Stats Store (e.g. {"projects_completed": 5, "polls_voted": 10})
    stats = models.JSONField(default=dict, blank=True)

    last_activity_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "community")
        indexes = [
            models.Index(fields=["community", "-total_xp"]), # Leaderboard
        ]

    def __str__(self):
        return f"{self.user} @ {self.community}: {self.total_xp} XP (Lvl {self.current_level})"
