from rest_framework.response import Response
from rest_framework import status
from core.models import CommunityMembership
from events.models import EventTeamMember

def api_error(message: str, status_code=status.HTTP_400_BAD_REQUEST):
    """
    Small helper to standardize error responses across the events app.
    Always returns: {"error": "<message>"} with the given status code.
    """
    return Response({"error": message}, status=status_code)

def get_active_community_id_for_user(user):
    """
    Returns the ID of the user's active/default community, or None if not set.
    """
    membership = (
        CommunityMembership.objects
        .filter(user=user, is_active=True, is_default=True)
        .select_related("community")
        .first()
    )
    return membership.community_id if membership else None


def user_can_manage_event_team(user, event) -> bool:
    """
    True if user is a manager at community level (owner/admin/organizer)
    for the event's community.
    """
    if not user.is_authenticated:
        return False

    if not hasattr(event, "community") or event.community is None:
        return False

    try:
        membership = CommunityMembership.objects.get(
            community=event.community,
            user=user,
            is_active=True,
        )
    except CommunityMembership.DoesNotExist:
        return False

    return membership.role in (
        CommunityMembership.ROLE_OWNER,
        CommunityMembership.ROLE_ADMIN,
        CommunityMembership.ROLE_ORGANIZER,
    )


def user_can_manage_event_attendance(user, event):
    if not user or not getattr(user, "is_authenticated", False):
        return False

    # System-level
    if user_is_system_admin(user):
        return True

    if not event:
        return False

    # Event organizer
    if getattr(event, "organizer_id", None) == user.id:
        return True

    # Community-level elevated roles
    if event.community_id:
        membership_exists = CommunityMembership.objects.filter(
            community=event.community,
            user=user,
            is_active=True,
            role__in=[
                CommunityMembership.ROLE_OWNER,
                CommunityMembership.ROLE_ORGANIZER,
                CommunityMembership.ROLE_ADMIN,
            ],
        ).exists()
        if membership_exists:
            return True

    # Event team roles allowed to handle attendance
    return EventTeamMember.objects.filter(
        event=event,
        user=user,
        is_active=True,
        role__in=[
            EventTeamMember.ROLE_HOST,
            EventTeamMember.ROLE_CO_HOST,
            EventTeamMember.ROLE_VOLUNTEER,
        ],
    ).exists()


def user_is_system_admin(user) -> bool:
    """
    Global/system manager flag based on user.role.
    Treats both 'organizer' and 'admin' (and superuser) as elevated.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "is_superuser", False):
        return True

    role = getattr(user, "role", None)
    return role in ("organizer", "admin")


def user_can_edit_event(user, event) -> bool:
    """
    Who can edit/delete the event or manage registrations/announcements?
    - direct event.organizer
    - global admin (user.role == 'admin')
    - community-level managers (owner/admin/organizer for event.community)
    - event team with host / co_host role
    """
    if not user.is_authenticated:
        return False

    # Direct organizer or global admin
    if user == event.organizer or user_is_system_admin(user):
        return True

    # Community-level roles
    if hasattr(event, "community") and event.community is not None:
        try:
            membership = CommunityMembership.objects.get(
                community=event.community,
                user=user,
                is_active=True,
            )
        except CommunityMembership.DoesNotExist:
            membership = None

        if membership and membership.role in (
            CommunityMembership.ROLE_OWNER,
            CommunityMembership.ROLE_ADMIN,
            CommunityMembership.ROLE_ORGANIZER,
        ):
            return True

    # Event team managers (host/co_host)
    return EventTeamMember.objects.filter(
        event=event,
        user=user,
        is_active=True,
        role__in=[EventTeamMember.ROLE_HOST, EventTeamMember.ROLE_CO_HOST],
    ).exists()


def user_can_view_event_analytics(user, event) -> bool:
    """
    For now, same set as 'edit event'.
    """
    return user_can_edit_event(user, event)

def is_member(user, community):
    return CommunityMembership.objects.filter(
        user=user,
        community=community,
        is_active=True
    ).exists()
