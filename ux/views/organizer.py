from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from ux.services.organizer import get_managed_events
from events.analytics import get_event_stats, get_community_stats
from events.models import Event
from core.models import CommunityMembership


class UXOrganizerEventsSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = get_managed_events(request.user)
        return Response({
            "meta": {"success": True},
            "data": data,
        })


from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

class UXOrganizerEventStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id):
        event = get_object_or_404(Event, pk=event_id)

        # 🔒 Permission check: user must manage this event
        if not (
            event.organizer_id == request.user.id
            or CommunityMembership.objects.filter(
                user=request.user,
                community=event.community,
                is_active=True,
                role__in=[
                    CommunityMembership.ROLE_OWNER,
                    CommunityMembership.ROLE_ADMIN,
                    CommunityMembership.ROLE_ORGANIZER,
                ],
            ).exists()
        ):
            raise PermissionDenied("You do not have access to this event")

        stats = get_event_stats(
            event=event,
            user=request.user,
        )

        return Response({
            "meta": {"success": True},
            "data": {
                "event_id": event.id,
                "stats": stats,
            },
        })


class UXOrganizerCommunityAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        community_id = (
            request.query_params.get("community_id")
            or request.headers.get("X-Community-ID")
        )

        if not community_id:
            return Response(
                {"error": "community_id required"},
                status=400,
            )

        stats = get_community_stats(
            user=request.user,
            community_id=community_id,
        )

        return Response({
            "meta": {"success": True},
            "data": {
                "community_id": int(community_id),
                "stats": stats,
            },
        })
