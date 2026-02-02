# cos-backend/events/state_machine.py
"""
Event State Machine for e-COS.

Enforces valid state transitions for event lifecycle:
draft → pending → approved → [published]
     └→ approved (owner shortcut)

Any transition not in VALID_TRANSITIONS is rejected.
"""
from typing import Tuple, Optional
import logging

from .models import Event

logger = logging.getLogger('cos.events')


# Valid state transitions: from_status -> list of allowed to_statuses
VALID_TRANSITIONS = {
    Event.STATUS_DRAFT: [Event.STATUS_PENDING, Event.STATUS_APPROVED],  # Owner can skip pending
    Event.STATUS_PENDING: [Event.STATUS_APPROVED, Event.STATUS_REJECTED],
    Event.STATUS_APPROVED: [Event.STATUS_REJECTED, Event.STATUS_PENDING],  # Can unpublish
    Event.STATUS_REJECTED: [Event.STATUS_PENDING, Event.STATUS_DRAFT],  # Can resubmit
}


def can_transition(event: Event, new_status: str) -> Tuple[bool, str]:
    """
    Check if an event can transition to a new status.

    Returns (can_transition: bool, reason: str)
    """
    current_status = event.status

    if new_status == current_status:
        return True, "Same status"

    if new_status not in dict(Event.STATUS_CHOICES):
        return False, f"Invalid status: {new_status}"

    allowed = VALID_TRANSITIONS.get(current_status, [])

    if new_status not in allowed:
        return False, f"Cannot transition from '{current_status}' to '{new_status}'"

    return True, ""


def transition(event: Event, new_status: str, actor=None, save: bool = True) -> Tuple[bool, str]:
    """
    Attempt to transition an event to a new status.

    Args:
        event: The event to transition
        new_status: The target status
        actor: The user performing the action (for logging)
        save: Whether to save the event after transitioning

    Returns (success: bool, message: str)
    """
    can, reason = can_transition(event, new_status)

    if not can:
        logger.warning(
            f"Invalid state transition attempted: event={event.id}, "
            f"from={event.status}, to={new_status}, actor={getattr(actor, 'id', 'unknown')}. "
            f"Reason: {reason}"
        )
        return False, reason

    old_status = event.status
    event.status = new_status

    if save:
        event.save(update_fields=['status'])

    logger.info(
        f"Event state transition: event={event.id}, "
        f"from={old_status}, to={new_status}, actor={getattr(actor, 'id', 'unknown')}"
    )

    return True, f"Transitioned from '{old_status}' to '{new_status}'"


def get_allowed_transitions(event: Event) -> list:
    """
    Get list of allowed status transitions for an event.
    """
    return VALID_TRANSITIONS.get(event.status, [])


def is_terminal_status(status: str) -> bool:
    """
    Check if a status is a terminal state (no further transitions).

    Note: Currently no truly terminal states exist; rejected can be resubmitted.
    """
    return status not in VALID_TRANSITIONS or len(VALID_TRANSITIONS[status]) == 0


def validate_action_for_status(event: Event, action: str) -> Tuple[bool, str]:
    """
    Validate if an action is allowed given the event's current status.

    Actions and their requirements:
    - 'register': Event must be APPROVED
    - 'edit': Event must not be in certain locked states
    - 'cancel': Event must not have started
    - 'scan_attendance': Event must be APPROVED
    - 'issue_certificate': Event must be past (ended)
    """
    from .datetime_utils import is_event_past, is_event_upcoming

    status = event.status

    if action == 'register':
        if status != Event.STATUS_APPROVED:
            return False, "Registration is only open for approved events"
        return True, ""

    elif action == 'edit':
        # Can edit in most states
        return True, ""

    elif action == 'cancel':
        if not is_event_upcoming(event):
            return False, "Cannot cancel an event that has already started"
        return True, ""

    elif action == 'scan_attendance':
        if status != Event.STATUS_APPROVED:
            return False, "Attendance can only be scanned for approved events"
        return True, ""

    elif action == 'issue_certificate':
        if status != Event.STATUS_APPROVED:
            return False, "Certificates can only be issued for approved events"
        if not is_event_past(event):
            return False, "Certificates can only be issued after the event has ended"
        return True, ""

    return True, ""  # Unknown actions are allowed by default
