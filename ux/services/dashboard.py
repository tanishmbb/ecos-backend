# ux/services/dashboard.py

from django.utils import timezone
from django.db.models import Q

from events.models import Event, EventRegistration, EventAttendance, Certificate
from notifications.models import Notification
from core.models import CommunityMembership


def get_dashboard_summary(user):
    now = timezone.now()

    # 1️⃣ Registrations
    registrations_qs = EventRegistration.objects.filter(user=user)
    total_registrations = registrations_qs.count()

    # 2️⃣ Events user is involved in
    base_events = Event.objects.filter(
        Q(organizer=user)
        | Q(eventregistration__user=user)
        | Q(team_members__user=user, team_members__is_active=True)
    ).distinct()

    upcoming_events = base_events.filter(start_time__gt=now).count()
    ongoing_events = base_events.filter(
        start_time__lte=now,
        end_time__gte=now,
    ).count()
    past_events = base_events.filter(end_time__lt=now).count()

    # 3️⃣ Attendance
    attended_events = EventAttendance.objects.filter(
        registration__user=user,
        check_in__isnull=False,
    ).values("registration__event").distinct().count()

    attendance_rate = (
        round((attended_events / total_registrations) * 100, 2)
        if total_registrations > 0
        else 0.0
    )

    # 4️⃣ Certificates
    certificates_earned = Certificate.objects.filter(
        registration__user=user
    ).count()

    # 5️⃣ Notifications
    unread_notifications = Notification.objects.filter(
        user=user,
        is_read=False,
    ).count()

    # 6️⃣ Communities
    communities_joined = CommunityMembership.objects.filter(
        user=user,
        is_active=True,
    ).count()

    return {
        "upcoming_events": upcoming_events,
        "ongoing_events": ongoing_events,
        "past_events": past_events,
        "total_registrations": total_registrations,
        "events_attended": attended_events,
        "attendance_rate": attendance_rate,
        "certificates_earned": certificates_earned,
        "unread_notifications": unread_notifications,
        "communities_joined": communities_joined,
    }
