from .models import EventRegistration, EventAttendance, Event

from django.utils import timezone
from django.db.models import Count, Avg

from core.models import Community, CommunityMembership
from .models import Event, EventRegistration, EventFeedback

# AFTER
def get_event_stats(*, event, user=None):
    event_id = event.id
    stats = {}

    total_regs = EventRegistration.objects.filter(event_id=event_id).count()
    stats["total_registrations"] = total_regs

    attendance = EventAttendance.objects.filter(registration__event_id=event_id)

    stats["checked_in"] = attendance.exclude(check_in=None).count()
    stats["checked_out"] = attendance.exclude(check_out=None).count()

    if total_regs > 0:
        stats["attendance_rate"] = round(
            (stats["checked_in"] / total_regs) * 100, 2
        )
    else:
        stats["attendance_rate"] = 0

    return stats
from .models import Event, EventRegistration, EventAttendance

def get_organizer_stats(user, community_id=None):
    """
    Aggregate stats for an organizer.
    If community_id is provided, limit to that community's events.
    """
    qs = Event.objects.filter(organizer=user)

    if community_id:
        qs = qs.filter(community_id=community_id)

    now = timezone.now()

    total_events = qs.count()
    upcoming_events = qs.filter(start_time__gte=now).count()
    past_events = qs.filter(end_time__lt=now).count()

    total_registrations = EventRegistration.objects.filter(event__in=qs).count()

    feedback_qs = EventFeedback.objects.filter(event__in=qs)
    feedback_agg = feedback_qs.aggregate(
        avg_rating=Avg("rating"),
        total_feedback=Count("id"),
    )

    return {
        "total_events": total_events,
        "upcoming_events": upcoming_events,
        "past_events": past_events,
        "total_registrations": total_registrations,
        "average_rating": feedback_agg["avg_rating"],
        "total_feedback": feedback_agg["total_feedback"],
    }
def get_community_stats(community: Community):
    """
    High-level stats for a community (for owners/admins/organizers).
    """

    now = timezone.now()

    events_qs = Event.objects.filter(community=community)
    total_events = events_qs.count()
    upcoming_events = events_qs.filter(start_time__gte=now).count()
    past_events = events_qs.filter(end_time__lt=now).count()

    total_registrations = EventRegistration.objects.filter(
        event__community=community
    ).count()

    active_members = CommunityMembership.objects.filter(
        community=community,
        is_active=True,
    ).count()

    feedback_qs = EventFeedback.objects.filter(event__community=community)
    feedback_agg = feedback_qs.aggregate(
        avg_rating=Avg("rating"),
        total_feedback=Count("id"),
    )

    return {
        "total_events": total_events,
        "upcoming_events": upcoming_events,
        "past_events": past_events,
        "total_registrations": total_registrations,
        "active_members": active_members,
        "average_rating": feedback_agg["avg_rating"],
        "total_feedback": feedback_agg["total_feedback"],
    }
