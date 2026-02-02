# ux/services/dashboard_communities.py

from django.utils import timezone
from django.db.models import Count

from core.models import CommunityMembership
from core.models import CommunityMembership
from events.models import Event


def get_dashboard_communities(user):
    now = timezone.now()

    memberships = (
        CommunityMembership.objects
        .select_related("community")
        .filter(user=user, is_active=True)
    )

    community_ids = [m.community_id for m in memberships]

    # Upcoming events count per community
    upcoming_event_counts = {
        item["community"]: item["count"]
        for item in (
            Event.objects
            .filter(
                community_id__in=community_ids,
                start_time__gt=now,
                status=Event.STATUS_APPROVED,
            )
            .values("community")
            .annotate(count=Count("id"))
        )
    }

    communities = []

    for membership in memberships:
        community = membership.community

        communities.append({
            "id": community.id,
            "name": community.name,
            "description": community.description,
            "slug": community.slug,
            "role": membership.role,
            "is_default": getattr(membership, "is_default", False),
            "upcoming_events": upcoming_event_counts.get(community.id, 0),
        })

    return {
        "communities": communities,
        "total": len(communities),
    }
