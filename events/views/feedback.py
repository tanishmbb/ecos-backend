from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count, Avg

from events.models import Event, EventRegistration, EventFeedback
from events import serializers as event_serializers
from events.throttles import CommunityEventCreateThrottle
from .generics import api_error, user_can_edit_event, user_can_view_event_analytics

class SubmitFeedbackView(APIView):
    """
    POST /api/v1/events/<event_id>/feedback/submit/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, event_id):
        event = get_object_or_404(Event, pk=event_id)

        is_registered = EventRegistration.objects.filter(
            event=event, user=request.user
        ).exists()
        if not is_registered:
            return Response(
                {"error": "You are not registered for this event"},
                status=status.HTTP_403_FORBIDDEN,
            )

        now = timezone.now()
        if event.start_time > now:
            return Response(
                {"error": "You can only give feedback after the event starts"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing = EventFeedback.objects.filter(
            event=event,
            user=request.user,
        ).first()

        if existing:
            serializer = event_serializers.EventFeedbackSerializer(
                existing,
                data=request.data,
                partial=True,
            )
        else:
            serializer = event_serializers.EventFeedbackSerializer(
                data=request.data,
            )

        if serializer.is_valid():
            feedback = serializer.save(
                event=event,
                user=request.user,
            )
            return Response(
                event_serializers.EventFeedbackSerializer(feedback).data,
                status=status.HTTP_201_CREATED if not existing else status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EventFeedbackListView(APIView):
    """
    GET /api/v1/events/<event_id>/feedback/
    - Only event managers can view all feedback for an event.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [CommunityEventCreateThrottle]

    def get(self, request, event_id):
        event = get_object_or_404(Event, pk=event_id)

        if not user_can_edit_event(request.user, event):
            return api_error(
                "Not allowed to view feedback for this event.",
                status.HTTP_403_FORBIDDEN,
            )

        feedback_qs = (
            EventFeedback.objects
            .select_related("user", "event")
            .filter(event=event)
            .order_by("-created_at")
        )

        # Pagination
        total_count = feedback_qs.count()
        limit = int(request.query_params.get("limit", 50))
        offset = int(request.query_params.get("offset", 0))
        limit = max(1, min(limit, 100))
        offset = max(0, offset)

        feedback_qs = feedback_qs[offset : offset + limit]

        serializer = event_serializers.EventFeedbackSerializer(feedback_qs, many=True)
        return Response({
            "count": total_count,
            "results": serializer.data,
            "limit": limit,
            "offset": offset,
        }, status=status.HTTP_200_OK)


class EventFeedbackStatsView(APIView):
    """
    GET /api/v1/events/<event_id>/feedback/stats/
    - Only event managers (same as analytics).
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [CommunityEventCreateThrottle]

    def get(self, request, event_id):
        event = get_object_or_404(Event, pk=event_id)

        if not user_can_view_event_analytics(request.user, event):
            return api_error(
                "Not allowed to view feedback stats for this event.",
                status.HTTP_403_FORBIDDEN,
            )

        qs = EventFeedback.objects.filter(event=event)

        agg = qs.aggregate(
            avg_rating=Avg("rating"),
            total=Count("id"),
        )

        dist = (
            qs.values("rating")
            .annotate(count=Count("id"))
            .order_by("-rating")
        )

        return Response(
            {
                "event": event.title,
                "average_rating": agg["avg_rating"],
                "total_feedback": agg["total"],
                "distribution": list(dist),
            },
            status=status.HTTP_200_OK,
        )
