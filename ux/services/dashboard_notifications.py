# ux/services/dashboard_notifications.py

from notifications.models import Notification


def get_dashboard_notifications(user, limit=30):
    qs = (
        Notification.objects
        .filter(user=user)
        .select_related("event")
        .order_by("-created_at")
    )

    notifications = [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "body": n.body,
            "event_id": n.event_id,
            "is_read": n.is_read,
            "created_at": n.created_at,
        }
        for n in qs[:limit]
    ]

    unread_count = qs.filter(is_read=False).count()

    return {
        "unread_count": unread_count,
        "notifications": notifications,
    }


def mark_notifications_read(user, ids=None):
    qs = Notification.objects.filter(user=user, is_read=False)

    if ids:
        qs = qs.filter(id__in=ids)

    updated = qs.update(is_read=True)
    return updated
