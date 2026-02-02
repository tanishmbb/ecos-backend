# ux/services/event_discovery.py

from django.utils import timezone
from django.db.models import Count

from events.models import Event, EventRegistration
from core.models import CommunityMembership


DEFAULT_LIMIT = 20


def serialize_event_card(event, reg_count_map):
    return {
        "id": event.id,
        "title": event.title,
        "start_time": event.start_time,
        "end_time": event.end_time,
        "community_id": event.community_id,
        "is_public": event.is_public,
        "registrations_count": reg_count_map.get(event.id, 0),
    }


def get_registration_counts(event_ids):
    return {
        item["event"]: item["count"]
        for item in (
            EventRegistration.objects
            .filter(event_id__in=event_ids)
            .values("event")
            .annotate(count=Count("id"))
        )
    }


# 1️⃣ UPCOMING EVENTS (GLOBAL)
def get_upcoming_events(limit=DEFAULT_LIMIT):
    now = timezone.now()

    qs = (
        Event.objects
        .filter(
            start_time__gt=now,
            status=Event.STATUS_APPROVED,
        )
        .order_by("start_time")[:limit]
    )

    reg_counts = get_registration_counts([e.id for e in qs])

    return [serialize_event_card(e, reg_counts) for e in qs]


# 2️⃣ EVENTS FROM USER COMMUNITIES
def get_my_community_events(user, limit=DEFAULT_LIMIT):
    now = timezone.now()

    community_ids = CommunityMembership.objects.filter(
        user=user,
        is_active=True,
    ).values_list("community_id", flat=True)

    qs = (
        Event.objects
        .filter(
            community_id__in=community_ids,
            start_time__gt=now,
            status=Event.STATUS_APPROVED,
        )
        .order_by("start_time")[:limit]
    )

    reg_counts = get_registration_counts([e.id for e in qs])

    return [serialize_event_card(e, reg_counts) for e in qs]


# 3️⃣ TRENDING EVENTS (RULE-BASED)
def get_trending_events(limit=DEFAULT_LIMIT):
    now = timezone.now()

    qs = (
        Event.objects
        .filter(
            start_time__gt=now,
            status=Event.STATUS_APPROVED,
        )
        .annotate(reg_count=Count("eventregistration"))
        .order_by("-reg_count", "start_time")[:limit]
    )

    reg_counts = {e.id: e.reg_count for e in qs}

    return [serialize_event_card(e, reg_counts) for e in qs]


# 4️⃣ RECOMMENDED EVENTS (RULE-BASED V1)
def get_recommended_events(user, limit=DEFAULT_LIMIT):
    now = timezone.now()

    community_ids = CommunityMembership.objects.filter(
        user=user,
        is_active=True,
    ).values_list("community_id", flat=True)

    qs = (
        Event.objects
        .filter(
            community_id__in=community_ids,
            start_time__gt=now,
            status=Event.STATUS_APPROVED,
        )
        .exclude(eventregistration__user=user)
        .annotate(reg_count=Count("eventregistration"))
        .order_by("-reg_count", "start_time")[:limit]
    )

    reg_counts = {e.id: e.reg_count for e in qs}

    return [serialize_event_card(e, reg_counts) for e in qs]
