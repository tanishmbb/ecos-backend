from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import DomainActivity
from core.services import ActivityService
from core.constants import ACTIVITY_PROJECT_CREATED
from .models import Project

@receiver(post_save, sender=Project)
def log_project_created(sender, instance, created, **kwargs):
    if created:
        ActivityService.log_activity(
            actor=instance.owner,
            verb=ACTIVITY_PROJECT_CREATED,
            target=instance,
            community=instance.community,
            visibility=DomainActivity.VISIBILITY_COMMUNITY,
            metadata={'title': instance.title, 'type': 'project'}
        )
