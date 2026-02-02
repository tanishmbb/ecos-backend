# ux/services/organizer.py

from django.db.models import Q
from django.utils import timezone

from events.models import Event, EventRegistration, EventAttendance, Certificate, EventFeedback
from core.models import CommunityMembership


def get_managed_events(user):
    """
    Returns all events the user can manage:
    - direct organizer
    - community owner/admin/organizer
    """

    # Communities where user has elevated role
    community_ids = CommunityMembership.objects.filter(
        user=user,
        is_active=True,
        role__in=[
            CommunityMembership.ROLE_OWNER,
            CommunityMembership.ROLE_ADMIN,
            CommunityMembership.ROLE_ORGANIZER,
        ],
    ).values_list("community_id", flat=True)

    # Proper queryset (THIS IS THE FIX)
    events_qs = (
        Event.objects
        .filter(
            Q(organizer=user) |
            Q(community_id__in=community_ids)
        )
        .distinct()
        .order_by("-start_time")
    )

    events = []

    for event in events_qs:
        registrations = EventRegistration.objects.filter(event=event).count()

        attended = EventAttendance.objects.filter(
            registration__event=event,
            check_in__isnull=False,
        ).count()

        attendance_rate = (
            round((attended / registrations) * 100, 2)
            if registrations > 0
            else 0.0
        )

        events.append({
            "id": event.id,
            "title": event.title,
            "start_time": event.start_time,
            "registrations": registrations,
            "attendance_rate": attendance_rate,
            "feedback_count": EventFeedback.objects.filter(event=event).count(),
            "certificates_issued": Certificate.objects.filter(
                registration__event=event
            ).count(),
        })

    return {
        "events": events,
        "total": len(events),
    }
