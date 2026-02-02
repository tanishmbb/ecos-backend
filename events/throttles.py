# events/throttles.py

from rest_framework.throttling import ScopedRateThrottle
from .models import Event


class CommunityEventCreateThrottle(ScopedRateThrottle):
    """
    Throttle event creation per user per community.

    Scope key: 'community-event-create'
    Cache key shape:
      throttle_community-event-create_u<user_id>_c<community_id or global>
    """
    scope = "community-event-create"

    def get_cache_key(self, request, view):
        # Only throttle POST (event creation)
        if request.method != "POST":
            return None

        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None

        # We rely on community_id passed in the payload or query
        community_id = request.data.get("community_id") or request.query_params.get("community_id")
        if not community_id:
            community_id = "global"

        return f"throttle_{self.scope}_u{user.id}_c{community_id}"


class CommunityAnnouncementCreateThrottle(ScopedRateThrottle):
    """
    Throttle announcement creation per user per community/event.

    Scope key: 'community-announcement-create'
    Cache key shape:
      throttle_community-announcement-create_u<user_id>_c<community_id>
    Falls back to event_id if community not found.
    """
    scope = "community-announcement-create"

    def get_cache_key(self, request, view):
        # Only throttle POST (announcement create)
        if request.method != "POST":
            return None

        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None

        # event_id from URL (EventAnnouncementListCreateView has event_id kwarg)
        event_id = getattr(view, "kwargs", {}).get("event_id")
        community_id = "unknown"

        if event_id:
            try:
                event = Event.objects.only("id", "community_id").get(id=event_id)
                community_id = event.community_id or f"event-{event_id}"
            except Event.DoesNotExist:
                community_id = f"event-{event_id}"

        return f"throttle_{self.scope}_u{user.id}_c{community_id}"


class CommunityAnalyticsThrottle(ScopedRateThrottle):
    """
    Throttle analytics access per user per community.

    Scope key: 'community-analytics'
    Cache key shape:
      throttle_community-analytics_u<user_id>_c<community_id or none>
    """
    scope = "community-analytics"

    def get_cache_key(self, request, view):
        # For now we throttle all methods (GET analytics)
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None

        # Try to detect community_id from query or header
        community_id = (
            request.query_params.get("community_id")
            or request.headers.get("X-Community-ID")
            or "none"
        )

        return f"throttle_{self.scope}_u{user.id}_c{community_id}"
