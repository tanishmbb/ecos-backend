from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
import logging

from .models import Event, EventRegistration, EventAttendance, Certificate, EventVolunteer, EventFeedback
from .activity_verbs import (
    EVENT_CREATED, EVENT_UPDATED, EVENT_APPROVED, EVENT_REJECTED,
    REGISTRATION_CREATED, REGISTRATION_CANCELED,
    ATTENDANCE_CHECK_IN, ATTENDANCE_CHECK_OUT,
    CERTIFICATE_ISSUED, FEEDBACK_SUBMITTED,
)
from core.services import ActivityService
from core.models import DomainActivity

logger = logging.getLogger('cos.events')


# Track status changes for Event
_event_status_cache = {}


@receiver(pre_save, sender=Event)
def cache_event_status(sender, instance, **kwargs):
    """Cache old status before save to detect transitions."""
    if instance.pk:
        try:
            old_instance = Event.objects.get(pk=instance.pk)
            _event_status_cache[instance.pk] = old_instance.status
        except Event.DoesNotExist:
            pass


@receiver(post_save, sender=Event)
def log_event_activity(sender, instance, created, **kwargs):
    """Log event lifecycle activities."""
    try:
        if created:
            ActivityService.log_activity(
                actor=instance.organizer,
                verb=EVENT_CREATED,
                target=instance,
                community=instance.community,
                metadata={'event_title': instance.title, 'status': instance.status}
            )
            logger.info(f"Activity logged: event.created for event {instance.id}")
        else:
            # Check for status change
            old_status = _event_status_cache.pop(instance.pk, None)
            if old_status and old_status != instance.status:
                if instance.status == Event.STATUS_APPROVED:
                    ActivityService.log_activity(
                        actor=instance.organizer,  # Could be approver, but we don't track that here
                        verb=EVENT_APPROVED,
                        target=instance,
                        community=instance.community,
                        visibility=DomainActivity.VISIBILITY_PUBLIC,
                        metadata={'event_title': instance.title, 'old_status': old_status}
                    )
                    logger.info(f"Activity logged: event.approved for event {instance.id}")
                elif instance.status == Event.STATUS_REJECTED:
                    ActivityService.log_activity(
                        actor=instance.organizer,
                        verb=EVENT_REJECTED,
                        target=instance,
                        community=instance.community,
                        metadata={'event_title': instance.title, 'old_status': old_status}
                    )
                    logger.info(f"Activity logged: event.rejected for event {instance.id}")
    except Exception as e:
        logger.warning(f"Failed to log event activity: {e}")


@receiver(post_save, sender=EventRegistration)
def log_registration_activity(sender, instance, created, **kwargs):
    """Log registration activities."""
    if created:
        try:
            ActivityService.log_activity(
                actor=instance.user,
                verb=REGISTRATION_CREATED,
                target=instance,
                community=instance.event.community,
                metadata={
                    'event_title': instance.event.title,
                    'event_id': instance.event.id,
                    'guests_count': instance.guests_count
                }
            )
            logger.info(f"Activity logged: registration.created for user {instance.user.id}, event {instance.event.id}")
        except Exception as e:
            logger.warning(f"Failed to log registration activity: {e}")


@receiver(post_delete, sender=EventRegistration)
def log_registration_canceled(sender, instance, **kwargs):
    """Log registration cancellation."""
    try:
        ActivityService.log_activity(
            actor=instance.user,
            verb=REGISTRATION_CANCELED,
            target=instance.event,  # Link to event since registration is deleted
            community=instance.event.community,
            metadata={
                'event_title': instance.event.title,
                'event_id': instance.event.id,
            }
        )
        logger.info(f"Activity logged: registration.canceled for user {instance.user.id}, event {instance.event.id}")
    except Exception as e:
        logger.warning(f"Failed to log registration cancellation: {e}")


# Track attendance changes
_attendance_checkin_cache = {}


@receiver(pre_save, sender=EventAttendance)
def cache_attendance_state(sender, instance, **kwargs):
    """Cache old check-in state before save."""
    if instance.pk:
        try:
            old = EventAttendance.objects.get(pk=instance.pk)
            _attendance_checkin_cache[instance.pk] = {
                'check_in': old.check_in,
                'check_out': old.check_out,
            }
        except EventAttendance.DoesNotExist:
            pass


@receiver(post_save, sender=EventAttendance)
def log_attendance(sender, instance, created, **kwargs):
    """Log attendance check-in and check-out."""
    try:
        cached = _attendance_checkin_cache.pop(instance.pk, {})
        old_check_in = cached.get('check_in')
        old_check_out = cached.get('check_out')

        # Log check-in (first time check_in is set)
        if instance.check_in and not old_check_in:
            # Avoid duplicate logging
            exists = DomainActivity.objects.filter(
                verb=ATTENDANCE_CHECK_IN,
                object_id=instance.pk,
                content_type=ContentType.objects.get_for_model(EventAttendance)
            ).exists()

            if not exists:
                event = instance.registration.event
                ActivityService.log_activity(
                    actor=instance.registration.user,
                    verb=ATTENDANCE_CHECK_IN,
                    target=instance,
                    community=event.community,
                    metadata={'event_title': event.title}
                )
                logger.info(f"Activity logged: attendance.check_in for attendance {instance.id}")

        # Log check-out (first time check_out is set)
        if instance.check_out and not old_check_out:
            exists = DomainActivity.objects.filter(
                verb=ATTENDANCE_CHECK_OUT,
                object_id=instance.pk,
                content_type=ContentType.objects.get_for_model(EventAttendance)
            ).exists()

            if not exists:
                event = instance.registration.event
                ActivityService.log_activity(
                    actor=instance.registration.user,
                    verb=ATTENDANCE_CHECK_OUT,
                    target=instance,
                    community=event.community,
                    metadata={'event_title': event.title}
                )
                logger.info(f"Activity logged: attendance.check_out for attendance {instance.id}")

    except Exception as e:
        logger.warning(f"Failed to log attendance activity: {e}")


@receiver(post_save, sender=Certificate)
def log_certificate(sender, instance, created, **kwargs):
    """Log certificate issuance."""
    if created:
        try:
            event = instance.registration.event
            ActivityService.log_activity(
                actor=instance.registration.user,
                verb=CERTIFICATE_ISSUED,
                target=instance,
                community=event.community,
                visibility=DomainActivity.VISIBILITY_PUBLIC,
                metadata={'event_title': event.title, 'certificate_id': str(instance.id)}
            )
            logger.info(f"Activity logged: certificate.issued for certificate {instance.id}")
        except Exception as e:
            logger.warning(f"Failed to log certificate activity: {e}")


@receiver(post_save, sender=EventFeedback)
def log_feedback(sender, instance, created, **kwargs):
    """Log feedback submission."""
    if created:
        try:
            ActivityService.log_activity(
                actor=instance.user,
                verb=FEEDBACK_SUBMITTED,
                target=instance,
                community=instance.event.community,
                metadata={
                    'event_title': instance.event.title,
                    'rating': instance.rating,
                }
            )
            logger.info(f"Activity logged: feedback.submitted for event {instance.event.id}")
        except Exception as e:
            logger.warning(f"Failed to log feedback activity: {e}")


@receiver(post_save, sender=EventVolunteer)
def log_volunteering(sender, instance, created, **kwargs):
    """Log volunteer completion."""
    if instance.status == 'completed':
        try:
            exists = DomainActivity.objects.filter(
                verb='volunteer.completed',
                object_id=instance.pk,
                content_type=ContentType.objects.get_for_model(EventVolunteer)
            ).exists()

            if not exists:
                ActivityService.log_activity(
                    actor=instance.user,
                    verb='volunteer.completed',
                    target=instance,
                    community=instance.event.community,
                    visibility=DomainActivity.VISIBILITY_PUBLIC,
                    metadata={
                        'event_title': instance.event.title,
                        'role': instance.role
                    }
                )
                logger.info(f"Activity logged: volunteer.completed for volunteer {instance.id}")
        except Exception as e:
            logger.warning(f"Failed to log volunteer activity: {e}")

