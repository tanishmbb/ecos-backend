# cos-backend/events/policies.py
"""
Centralized e-COS Policy Layer

All permission checks for e-COS actions are defined here.
Views should use these methods instead of inline permission logic.
"""
from typing import Tuple, Optional
from django.db.models import QuerySet

from core.models import CommunityMembership, Community
from .models import Event, EventRegistration, EventTeamMember


# Role hierarchies
ELEVATED_COMMUNITY_ROLES = [
    CommunityMembership.ROLE_OWNER,
    CommunityMembership.ROLE_ADMIN,
    CommunityMembership.ROLE_ORGANIZER,
]

EVENT_TEAM_MANAGEMENT_ROLES = [
    EventTeamMember.ROLE_HOST,
    EventTeamMember.ROLE_CO_HOST,
]


class EventPolicy:
    """
    Centralized permission checks for e-COS events.
    All methods return bool or (bool, str) with reason.
    """

    @staticmethod
    def is_system_admin(user) -> bool:
        """Check if user is a system-level admin."""
        if not user or not user.is_authenticated:
            return False
        return user.is_superuser or user.role == 'admin'

    @staticmethod
    def is_community_elevated(user, community: Optional[Community]) -> bool:
        """Check if user has elevated role (owner/admin/organizer) in community."""
        if not user or not user.is_authenticated or community is None:
            return False

        return CommunityMembership.objects.filter(
            user=user,
            community=community,
            role__in=ELEVATED_COMMUNITY_ROLES,
            is_active=True,
        ).exists()

    @staticmethod
    def is_event_team_manager(user, event: Event) -> bool:
        """Check if user is HOST or CO_HOST of the event."""
        if not user or not user.is_authenticated or event is None:
            return False

        return EventTeamMember.objects.filter(
            event=event,
            user=user,
            role__in=EVENT_TEAM_MANAGEMENT_ROLES,
            is_active=True,
        ).exists()

    @staticmethod
    def is_event_organizer(user, event: Event) -> bool:
        """Check if user is the event creator/organizer."""
        if not user or not user.is_authenticated or event is None:
            return False
        return event.organizer_id == user.id

    # ─────────────────────────────────────────────────────────────
    # Event CRUD
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def can_create_event(user, community: Optional[Community]) -> Tuple[bool, str]:
        """Check if user can create an event in the given community."""
        if not user or not user.is_authenticated:
            return False, "Authentication required"

        if EventPolicy.is_system_admin(user):
            return True, ""

        if community is None:
            return False, "Community required for event creation"

        if EventPolicy.is_community_elevated(user, community):
            return True, ""

        return False, "You do not have permission to create events in this community"

    @staticmethod
    def can_edit_event(user, event: Event) -> Tuple[bool, str]:
        """Check if user can edit the event."""
        if not user or not user.is_authenticated:
            return False, "Authentication required"

        if EventPolicy.is_system_admin(user):
            return True, ""

        if EventPolicy.is_event_organizer(user, event):
            return True, ""

        if EventPolicy.is_event_team_manager(user, event):
            return True, ""

        if event.community and EventPolicy.is_community_elevated(user, event.community):
            return True, ""

        return False, "You do not have permission to edit this event"

    @staticmethod
    def can_delete_event(user, event: Event) -> Tuple[bool, str]:
        """Check if user can delete the event."""
        if not user or not user.is_authenticated:
            return False, "Authentication required"

        if EventPolicy.is_system_admin(user):
            return True, ""

        if EventPolicy.is_event_organizer(user, event):
            return True, ""

        if event.community:
            # Only owner/admin can delete, not organizer
            membership = CommunityMembership.objects.filter(
                user=user,
                community=event.community,
                role__in=[CommunityMembership.ROLE_OWNER, CommunityMembership.ROLE_ADMIN],
                is_active=True,
            ).first()
            if membership:
                return True, ""

        return False, "You do not have permission to delete this event"

    @staticmethod
    def can_approve_event(user, event: Event) -> Tuple[bool, str]:
        """Check if user can approve/reject the event."""
        if not user or not user.is_authenticated:
            return False, "Authentication required"

        if EventPolicy.is_system_admin(user):
            return True, ""

        if event.community:
            # Only owner/admin can approve, not organizer
            membership = CommunityMembership.objects.filter(
                user=user,
                community=event.community,
                role__in=[CommunityMembership.ROLE_OWNER, CommunityMembership.ROLE_ADMIN],
                is_active=True,
            ).first()
            if membership:
                return True, ""

        return False, "You do not have permission to approve/reject this event"

    # ─────────────────────────────────────────────────────────────
    # Registration
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def can_register(user, event: Event) -> Tuple[bool, str]:
        """Check if user can register for the event."""
        if not user or not user.is_authenticated:
            return False, "Authentication required"

        if event.status != Event.STATUS_APPROVED:
            return False, "Event is not open for registration"

        # Check if already registered
        if EventRegistration.objects.filter(event=event, user=user).exists():
            return False, "Already registered"

        return True, ""

    @staticmethod
    def can_cancel_registration(user, registration: EventRegistration) -> Tuple[bool, str]:
        """Check if user can cancel a registration."""
        if not user or not user.is_authenticated:
            return False, "Authentication required"

        # User can cancel their own registration
        if registration.user_id == user.id:
            return True, ""

        # Event manager can cancel any registration
        can_edit, _ = EventPolicy.can_edit_event(user, registration.event)
        if can_edit:
            return True, ""

        return False, "You cannot cancel this registration"

    @staticmethod
    def can_manage_registrations(user, event: Event) -> Tuple[bool, str]:
        """Check if user can view/manage registrations for the event."""
        return EventPolicy.can_edit_event(user, event)

    # ─────────────────────────────────────────────────────────────
    # Attendance
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def can_scan_attendance(user, event: Event) -> Tuple[bool, str]:
        """Check if user can scan QR codes for attendance."""
        if not user or not user.is_authenticated:
            return False, "Authentication required"

        if EventPolicy.is_system_admin(user):
            return True, ""

        if EventPolicy.is_event_organizer(user, event):
            return True, ""

        # Any team member (including volunteers) can scan
        if EventTeamMember.objects.filter(
            event=event,
            user=user,
            is_active=True,
        ).exists():
            return True, ""

        if event.community and EventPolicy.is_community_elevated(user, event.community):
            return True, ""

        return False, "You do not have permission to scan attendance for this event"

    # ─────────────────────────────────────────────────────────────
    # Certificates
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def can_issue_certificate(user, event: Event, target_user=None) -> Tuple[bool, str]:
        """Check if user can issue certificates for the event."""
        if not user or not user.is_authenticated:
            return False, "Authentication required"

        # Must be able to manage the event
        can_edit, reason = EventPolicy.can_edit_event(user, event)
        if not can_edit:
            return False, reason

        return True, ""

    # ─────────────────────────────────────────────────────────────
    # Analytics
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def can_view_analytics(user, event: Event) -> Tuple[bool, str]:
        """Check if user can view analytics for the event."""
        return EventPolicy.can_edit_event(user, event)

    @staticmethod
    def can_view_organizer_analytics(user, community: Optional[Community] = None) -> Tuple[bool, str]:
        """Check if user can view organizer-level analytics."""
        if not user or not user.is_authenticated:
            return False, "Authentication required"

        if EventPolicy.is_system_admin(user):
            return True, ""

        if community and EventPolicy.is_community_elevated(user, community):
            return True, ""

        # Check if user has any elevated role in any community
        if CommunityMembership.objects.filter(
            user=user,
            role__in=ELEVATED_COMMUNITY_ROLES,
            is_active=True,
        ).exists():
            return True, ""

        return False, "You do not have permission to view organizer analytics"

    # ─────────────────────────────────────────────────────────────
    # Announcements & Feedback
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def can_create_announcement(user, event: Event) -> Tuple[bool, str]:
        """Check if user can create announcements for the event."""
        return EventPolicy.can_edit_event(user, event)

    @staticmethod
    def can_submit_feedback(user, event: Event) -> Tuple[bool, str]:
        """Check if user can submit feedback for the event."""
        if not user or not user.is_authenticated:
            return False, "Authentication required"

        # Must be registered and have attended
        registration = EventRegistration.objects.filter(
            event=event,
            user=user,
        ).select_related('attendance').first()

        if not registration:
            return False, "You must be registered to submit feedback"

        # Check if attended (has check_in time)
        if hasattr(registration, 'attendance') and registration.attendance.check_in:
            return True, ""

        # Also allow if status is ATTENDED
        if registration.status == EventRegistration.STATUS_ATTENDED:
            return True, ""

        return False, "You must attend the event to submit feedback"

    # ─────────────────────────────────────────────────────────────
    # Team Management
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def can_manage_team(user, event: Event) -> Tuple[bool, str]:
        """Check if user can add/remove team members."""
        if not user or not user.is_authenticated:
            return False, "Authentication required"

        if EventPolicy.is_system_admin(user):
            return True, ""

        if EventPolicy.is_event_organizer(user, event):
            return True, ""

        # Only HOST can manage team (not CO_HOST)
        if EventTeamMember.objects.filter(
            event=event,
            user=user,
            role=EventTeamMember.ROLE_HOST,
            is_active=True,
        ).exists():
            return True, ""

        if event.community and EventPolicy.is_community_elevated(user, event.community):
            return True, ""

        return False, "You do not have permission to manage the event team"
