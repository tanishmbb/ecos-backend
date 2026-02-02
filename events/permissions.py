from rest_framework.permissions import BasePermission, SAFE_METHODS
from core.models import Community, CommunityMembership
from .models import EventTeamMember


# ---- Helper functions -------------------------------------------------


def is_global_organizer_or_admin(user) -> bool:
    """
    DEPRECATED.
    Always returns False to enforce community-only permissions.
    """
    return False


ELEVATED_COMMUNITY_ROLES = [
    CommunityMembership.ROLE_OWNER,
    CommunityMembership.ROLE_ADMIN,
    CommunityMembership.ROLE_ORGANIZER,
]


def is_community_elevated(user, community) -> bool:
    """
    Check if user has an elevated role in a given community.
    (owner / admin / organizer)
    """
    if not user or not user.is_authenticated or community is None:
        return False

    return CommunityMembership.objects.filter(
        user=user,
        community=community,
        role__in=ELEVATED_COMMUNITY_ROLES,
        is_active=True,
    ).exists()


def is_event_team(user, event) -> bool:
    """
    Check if user is part of the event team (host / co_host / volunteer).
    """
    if not user or not user.is_authenticated or event is None:
        return False

    return EventTeamMember.objects.filter(
        event=event,
        user=user,
        is_active=True,
    ).exists()


# ---- Permission classes -----------------------------------------------


class IsEventManager(BasePermission):
    """
    For event-scoped management endpoints:
    - SAFE methods: Allowed for everyone (filtered by visibility in views).
    - Write operations require context-aware permission:
        * User must have ELEVATED role (owner/admin/organizer) in the event's community.
        * OR user must be the event organizer (creator).
        * OR user must be an active EventTeamMember (host/co-host).

    DEPRECATED: Global user.role is NO LONGER CHECKED.
    """

    def has_permission(self, request, view):
        # Allow safe methods (GET, HEAD, OPTIONS) at list level
        # Visibility filtering happens in the queryset, not here.
        if request.method in SAFE_METHODS:
            return True

        if not request.user or not request.user.is_authenticated:
            return False

        # For creation (POST), we need to check the target community.
        # This is often passed in request.data['community_id']
        if request.method == "POST":
            # If creating an event, they must have permissions in the target community
            community_id = request.data.get("community_id")
            if community_id:
                # We can't easily check DB here without parsing, but the View usually handles
                # "membership check" for POST. Ideally, we move that logic here or keep it in view.
                # For strictness, let's allow the view to handle proper validation or check if we can load it.
                return True

        return True

    def has_object_permission(self, request, view, obj):
        # Read-only allowed (filtered by view queryset)
        if request.method in SAFE_METHODS:
            return True

        user = request.user
        if not user or not user.is_authenticated:
            return False

        # 1. Resolve Event & Community
        event = getattr(obj, "event", None)
        community = getattr(obj, "community", None)

        if isinstance(obj, Community):
            community = obj
        elif isinstance(obj, Event):
            event = obj
            community = obj.community
        elif event:
            community = event.community

        # 2. Check Event Level Permissions
        if event:
            # A. Access by creator/organizer
            if event.organizer_id == user.id:
                return True

            # B. Access by Event Team (Host/Co-Host only)
            if EventTeamMember.objects.filter(
                event=event,
                user=user,
                is_active=True,
                role__in=[EventTeamMember.ROLE_HOST, EventTeamMember.ROLE_CO_HOST]
            ).exists():
                return True

        # 3. Check Community Level Permissions (The "Parent" Authority)
        # If the event belongs to a community, Community Admins/Organizers override everything.
        if community:
            if is_community_elevated(user, community):
                return True

        return False


class IsCommunityManager(BasePermission):
    """
    For community management endpoints (members, overview edits, etc.):
    - SAFE methods allowed for everyone (filtered by visibility).
    - Write operations require ELEVATED community role (owner/admin/organizer).

    DEPRECATED: Global user.role is NO LONGER CHECKED.
    """

    def has_permission(self, request, view):
        # Allow safe methods (GET, OPTIONS) list
        if request.method in SAFE_METHODS:
            return True

        if not request.user or not request.user.is_authenticated:
            return False

        return True

    def has_object_permission(self, request, view, obj):
        # Read-only allowed (filtered by view logic later)
        if request.method in SAFE_METHODS:
            return True

        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Resolve community from object
        community = None
        if isinstance(obj, Community):
            community = obj
        else:
            community = getattr(obj, "community", None)

        if not community:
            return False

        # Community-level elevated roles ONLY
        if is_community_elevated(user, community):
            return True

        return False
