from django.db.models.signals import post_save
from django.dispatch import receiver
from events.models import Event
from core.models import Announcement, FeedItem

@receiver(post_save, sender=Event)
def create_event_feed_item(sender, instance, created, **kwargs):
    # Only create feed item if event is APPROVED
    if instance.status == Event.STATUS_APPROVED:
        # Check if feed item already exists to avoid duplicates
        if not FeedItem.objects.filter(event=instance).exists():
            FeedItem.objects.create(type='event', event=instance)

@receiver(post_save, sender=Announcement)
def create_announcement_feed_item(sender, instance, created, **kwargs):
    if created:
        FeedItem.objects.create(type='announcement', announcement=instance)
