# core/analytics.py
# Analytics tracking service for Supabase

import os
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger("cos")


def _get_client():
    """Get Supabase client lazily."""
    from core.supabase_client import get_supabase_client
    return get_supabase_client()


def track_event(
    action: str,
    event_id: int | str | None = None,
    user_id: int | str | None = None,
    community_id: int | str | None = None,
    metadata: dict[str, Any] | None = None
) -> bool:
    """
    Track an analytics event to Supabase.

    Note: Django uses integer IDs while Supabase tables expect UUIDs.
    We store Django IDs in the metadata JSON field instead of UUID columns.

    Args:
        action: The action type (e.g., "registration", "qr_scan", "certificate_issued")
        event_id: Optional event ID (Django integer)
        user_id: Optional user ID (Django integer)
        community_id: Optional community ID (Django integer)
        metadata: Optional additional metadata

    Returns:
        True if tracking succeeded, False otherwise
    """
    client = _get_client()
    if not client:
        logger.debug("Supabase client not available, skipping analytics")
        return False

    try:
        # Store Django integer IDs in metadata (Supabase columns expect UUID)
        enriched_metadata = metadata.copy() if metadata else {}
        enriched_metadata.update({
            "django_event_id": event_id,
            "django_user_id": user_id,
            "django_community_id": community_id,
        })

        data = {
            "action": action,
            # event_id, user_id, community_id left as null (UUID columns)
            "metadata": enriched_metadata,
            "created_at": datetime.now().isoformat()
        }

        result = client.table("event_analytics").insert(data).execute()
        logger.debug(f"Tracked analytics event: {action}")
        return True
    except Exception as e:
        logger.error(f"Failed to track analytics: {e}")
        return False


def track_registration(event_id: int, user_id: int, community_id: int | None = None) -> bool:
    """Track a user registration for an event."""
    return track_event(
        action="registration",
        event_id=event_id,
        user_id=user_id,
        community_id=community_id,
        metadata={"type": "event_registration"}
    )


def track_qr_scan(event_id: int, user_id: int, scanned_by: int | None = None) -> bool:
    """Track a QR code scan (check-in)."""
    return track_event(
        action="qr_scan",
        event_id=event_id,
        user_id=user_id,
        metadata={"scanned_by": scanned_by}
    )


def track_certificate_issued(
    event_id: int,
    user_id: int,
    cert_id: int,
    community_id: int | None = None
) -> bool:
    """Track a certificate issuance."""
    return track_event(
        action="certificate_issued",
        event_id=event_id,
        user_id=user_id,
        community_id=community_id,
        metadata={"certificate_id": cert_id}
    )


def get_event_analytics(event_id: int) -> list[dict]:
    """
    Get analytics data for a specific event.

    Args:
        event_id: The event ID

    Returns:
        List of analytics records
    """
    client = _get_client()
    if not client:
        return []

    try:
        result = client.table("event_analytics")\
            .select("*")\
            .eq("event_id", str(event_id))\
            .order("created_at", desc=True)\
            .execute()

        return result.data if result.data else []
    except Exception as e:
        logger.error(f"Failed to get event analytics: {e}")
        return []


def get_analytics_summary(event_id: int) -> dict:
    """
    Get analytics summary for an event.

    Returns counts of registrations, QR scans, and certificates.
    """
    client = _get_client()
    if not client:
        return {"registrations": 0, "qr_scans": 0, "certificates": 0}

    try:
        # Get all analytics for this event
        result = client.table("event_analytics")\
            .select("action")\
            .eq("event_id", str(event_id))\
            .execute()

        data = result.data if result.data else []

        return {
            "registrations": sum(1 for r in data if r["action"] == "registration"),
            "qr_scans": sum(1 for r in data if r["action"] == "qr_scan"),
            "certificates": sum(1 for r in data if r["action"] == "certificate_issued"),
        }
    except Exception as e:
        logger.error(f"Failed to get analytics summary: {e}")
        return {"registrations": 0, "qr_scans": 0, "certificates": 0}
