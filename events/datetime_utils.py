# cos-backend/events/datetime_utils.py
"""
Centralized datetime handling for e-COS.

All datetime operations should use these utilities to ensure consistency
across the application and prepare for future USE_TZ=True migration.
"""
from datetime import datetime, timedelta
from typing import Optional
from django.utils import timezone


def now() -> datetime:
    """
    Get current datetime (timezone-aware when USE_TZ=True).

    This is the single source of truth for "now" in e-COS.
    """
    return timezone.now()


def is_event_upcoming(event) -> bool:
    """Check if event hasn't started yet."""
    if not event.start_time:
        return False
    return event.start_time > now()


def is_event_ongoing(event) -> bool:
    """Check if event is currently happening."""
    if not event.start_time or not event.end_time:
        return False
    current = now()
    return event.start_time <= current <= event.end_time


def is_event_past(event) -> bool:
    """Check if event has ended."""
    if not event.end_time:
        return False
    return event.end_time < now()


def format_for_api(dt: Optional[datetime]) -> Optional[str]:
    """
    Format datetime for API responses (ISO 8601).

    Returns None if input is None.
    """
    if dt is None:
        return None
    return dt.isoformat()


def format_for_display(dt: Optional[datetime], format_str: str = "%b %d, %Y %I:%M %p") -> Optional[str]:
    """
    Format datetime for human-readable display.

    Default format: "Jan 01, 2026 02:30 PM"
    """
    if dt is None:
        return None
    return dt.strftime(format_str)


def parse_iso(iso_string: str) -> Optional[datetime]:
    """
    Parse ISO 8601 datetime string.

    Returns None if parsing fails.
    """
    if not iso_string:
        return None
    try:
        return datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return None


def event_duration(event) -> Optional[timedelta]:
    """Get event duration as timedelta."""
    if not event.start_time or not event.end_time:
        return None
    return event.end_time - event.start_time


def event_duration_hours(event) -> Optional[float]:
    """Get event duration in hours."""
    duration = event_duration(event)
    if duration is None:
        return None
    return duration.total_seconds() / 3600


def is_registration_open(event, window_hours_before: int = 0) -> bool:
    """
    Check if registration is currently open for an event.

    Registration is open if:
    - Event is in APPROVED status
    - Event hasn't ended
    - Current time is before start (minus optional window)
    """
    from .models import Event

    if event.status != Event.STATUS_APPROVED:
        return False

    current = now()

    if event.end_time and current > event.end_time:
        return False

    if window_hours_before > 0 and event.start_time:
        cutoff = event.start_time - timedelta(hours=window_hours_before)
        if current > cutoff:
            return False

    return True


def days_until_event(event) -> Optional[int]:
    """Get number of days until event starts."""
    if not event.start_time:
        return None
    diff = event.start_time - now()
    return max(0, diff.days)
