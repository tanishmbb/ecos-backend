from django.contrib.contenttypes.models import ContentType
from .models import DomainActivity
from gamification.engine import ReputationEngine
from django.db import transaction

class ActivityService:
    @staticmethod
    def log_activity(actor, verb, target, community=None, visibility=DomainActivity.VISIBILITY_COMMUNITY, metadata=None):
        """
        Logs a domain activity and triggers side effects (Reputation, Notifications).
        """
        if metadata is None:
            metadata = {}

        # Create the immutable record
        activity = DomainActivity.objects.create(
            actor=actor,
            verb=verb,
            content_type=ContentType.objects.get_for_model(target),
            object_id=target.pk,
            community=community,
            visibility=visibility,
            metadata=metadata
        )

        # Trigger Reputation Engine (Side Effect)
        # We do this synchronously for now for simplicity, but in high-scale this goes to Celery
        transaction.on_commit(lambda: ReputationEngine.process_activity(activity))

        return activity
