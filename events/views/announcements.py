from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone

from events.models import Event, EventRegistration, Announcement
from notifications.models import Notification
from events import serializers as event_serializers
from events.throttles import CommunityEventCreateThrottle
from events.tasks import send_announcement_email_task
from events.emails import send_announcement_email
from .generics import user_can_edit_event, get_active_community_id_for_user

class EventAnnouncementListCreateView(APIView):
    """
    GET  /api/v1/events/<event_id>/announcements/
    POST /api/v1/events/<event_id>/announcements/
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [CommunityEventCreateThrottle]

    def get_event(self, event_id):
        return get_object_or_404(Event, pk=event_id)

    def get(self, request, event_id):
        event = self.get_event(event_id)

        is_manager = user_can_edit_event(request.user, event)
        is_registered = EventRegistration.objects.filter(
            event=event,
            user=request.user,
        ).exists()

        if not (is_manager or is_registered):
            return Response({"error": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        announcements = (
            Announcement.objects
            .select_related("posted_by", "event")
            .filter(event=event)
            .order_by("-created_at")
        )

        # Pagination
        total_count = announcements.count()
        limit = int(request.query_params.get("limit", 50))
        offset = int(request.query_params.get("offset", 0))
        limit = max(1, min(limit, 100))
        offset = max(0, offset)

        announcements = announcements[offset : offset + limit]

        serializer = event_serializers.AnnouncementSerializer(announcements, many=True)
        return Response({
            "count": total_count,
            "results": serializer.data,
            "limit": limit,
            "offset": offset,
        }, status=status.HTTP_200_OK)

    def post(self, request, event_id):
        event = self.get_event(event_id)

        if not user_can_edit_event(request.user, event):
            return Response(
                {"error": "Only event managers can create announcements"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = event_serializers.AnnouncementSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        announcement = serializer.save(
            event=event,
            posted_by=request.user,
        )
        reg_users = EventRegistration.objects.filter(event=event).select_related("user")

        bulk_notifications = [
            Notification(
                user=reg.user,
                event=event,
                type=Notification.TYPE_EVENT_ANNOUNCEMENT,
                title=f"New announcement for {event.title}",
                body=announcement.title,
            )
            for reg in reg_users
        ]

        Notification.objects.bulk_create(bulk_notifications, ignore_conflicts=True)

        try:
            send_announcement_email_task.delay(announcement.id)
        except Exception:
            try:
                send_announcement_email(announcement, request=request)
            except Exception:
                pass

        out = event_serializers.AnnouncementSerializer(announcement).data
        return Response(out, status=status.HTTP_201_CREATED)


class MyAnnouncementsView(APIView):
    """
    GET /api/v1/events/me/announcements/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        community_id = request.query_params.get("community_id")

        regs_qs = EventRegistration.objects.filter(user=request.user)

        if not community_id:
            community_id = get_active_community_id_for_user(request.user)

        if community_id:
            regs_qs = regs_qs.filter(event__community_id=community_id)

        event_ids = (
            regs_qs
            .values_list("event_id", flat=True)
            .distinct()
        )

        announcements = (
            Announcement.objects
            .select_related("event", "posted_by")
            .filter(event_id__in=event_ids)
            .order_by("-created_at")
        )

        serializer = event_serializers.AnnouncementSerializer(announcements, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
