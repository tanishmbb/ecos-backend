from django.db import transaction
from core.constants import (
    ACTIVITY_EVENT_ATTENDED,
    ACTIVITY_EVENT_CREATED,
    ACTIVITY_EVENT_PUBLISHED,
    ACTIVITY_MEMBER_JOINED,
    ACTIVITY_CERTIFICATE_ISSUED,
    ACTIVITY_PENALTY,
    ACTIVITY_MANUAL_ADJUSTMENT,
)
from .models import ReputationLog, UserCommunityStats

class ReputationEngine:
    # Point mapping config
    POINTS_MAP = {
        ACTIVITY_EVENT_ATTENDED: 10,
        ACTIVITY_EVENT_CREATED: 50, # Awarded when event approved/published? Or just created? Let's say Published.
        ACTIVITY_EVENT_PUBLISHED: 50,
        ACTIVITY_CERTIFICATE_ISSUED: 15,
        ACTIVITY_MEMBER_JOINED: 5, # Small welcome bonus
    }

    @classmethod
    def process_activity(cls, activity):
        """
        Analyzes an activity and awards points if applicable.
        Idempotency should be handled by checking if a log already exists for this activity.
        """
        points = cls.POINTS_MAP.get(activity.verb)

        # Handle dynamic points (penalties/adjustments)
        if activity.verb in [ACTIVITY_PENALTY, ACTIVITY_MANUAL_ADJUSTMENT]:
            points = activity.metadata.get('xp_change', 0)

        if points is None: # Changed from 'not points' to 'points is None' to allow 0 points explicitly
            return

        # Context is required for reputation (must act within a community)
        if not activity.community:
            return

        with transaction.atomic():
            # Check idempotency
            if ReputationLog.objects.filter(activity=activity).exists():
                return

            # Log the transaction
            ReputationLog.objects.create(
                user=activity.actor,
                community=activity.community,
                amount=points,
                reason=activity.verb,
                activity=activity
            )

            # Update denormalized stats
            stats, created = UserCommunityStats.objects.get_or_create(
                user=activity.actor,
                community=activity.community
            )
            stats.total_xp += points

            # Ensure Level/XP doesn't break on negatives (though we allow total_xp to drop, level floors at 1)
            # Leveling logic
            new_level = 1 + (max(0, stats.total_xp) // 100)
            stats.current_level = new_level

            # DEPRECATED: Event-specific columns (Keep for safety)
            stats.events_attended = stats.events_attended + (1 if activity.verb == ACTIVITY_EVENT_ATTENDED else 0)
            stats.events_hosted = stats.events_hosted + (1 if activity.verb in [ACTIVITY_EVENT_CREATED, ACTIVITY_EVENT_PUBLISHED] else 0)

            # 🔹 Generic Stats (New Source of Truth)
            # e.g. stats.stats['event.attended'] += 1
            if not stats.stats:
                stats.stats = {}

            current_val = stats.stats.get(activity.verb, 0)
            stats.stats[activity.verb] = current_val + 1

            stats.save()
