# ux/services/dashboard_events.py

from django.utils import timezone
from django.db.models import Q

from events.models import Event, EventRegistration, EventAttendance, Certificate


def get_dashboard_events(user):
    now = timezone.now()

    # All events user is involved in
    events_qs = Event.objects.filter(
        Q(organizer=user)
        | Q(eventregistration__user=user)
        | Q(team_members__user=user, team_members__is_active=True)
    ).distinct().select_related("community", "organizer")

    # Registrations map
    registrations = {
        reg.event_id: reg
        for reg in EventRegistration.objects.filter(
            user=user,
            event_id__in=events_qs.values_list("id", flat=True),
        )
    }

    # Attendance map
    attendance_map = {
        att.registration.event_id: att
        for att in EventAttendance.objects.filter(
            registration__user=user,
            registration__event_id__in=registrations.keys(),
        )
    }

    # Certificates map
    certificate_map = {
        cert.registration.event_id: cert
        for cert in Certificate.objects.filter(
            registration__user=user,
            registration__event_id__in=registrations.keys(),
        )
    }

    upcoming, ongoing, past = [], [], []

    for event in events_qs:
        reg = registrations.get(event.id)
        attendance = attendance_map.get(event.id)
        cert = certificate_map.get(event.id)

        event_data = {
            "id": event.id,
            "title": event.title,
            "start_time": event.start_time,
            "end_time": event.end_time,
            "community_id": event.community_id,
            "is_organizer": event.organizer_id == user.id,
            "is_registered": reg is not None,
            "attendance": {
                "checked_in": bool(attendance and attendance.check_in),
                "checked_out": bool(attendance and attendance.check_out),
            },
            "certificate_issued": cert is not None,
        }

        if event.start_time > now:
            upcoming.append(event_data)
        elif event.start_time <= now <= event.end_time:
            ongoing.append(event_data)
        else:
            past.append(event_data)

    # Optional ordering
    upcoming.sort(key=lambda e: e["start_time"])
    ongoing.sort(key=lambda e: e["start_time"])
    past.sort(key=lambda e: e["start_time"], reverse=True)

    return {
        "upcoming": upcoming,
        "ongoing": ongoing,
        "past": past,
    }
