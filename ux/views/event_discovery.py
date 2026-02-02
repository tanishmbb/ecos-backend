# ux/views/event_discovery.py

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from ux.services.event_discovery import (
    get_upcoming_events,
    get_my_community_events,
    get_trending_events,
    get_recommended_events,
)


class UXUpcomingEventsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        events = get_upcoming_events()
        return Response({
            "meta": {"success": True},
            "data": {
                "events": events,
                "count": len(events),
            },
        })


class UXMyCommunityEventsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        events = get_my_community_events(request.user)
        return Response({
            "meta": {"success": True},
            "data": {
                "events": events,
                "count": len(events),
            },
        })


class UXTrendingEventsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        events = get_trending_events()
        return Response({
            "meta": {"success": True},
            "data": {
                "events": events,
                "count": len(events),
            },
        })


class UXRecommendedEventsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        events = get_recommended_events(request.user)
        return Response({
            "meta": {"success": True},
            "data": {
                "events": events,
                "count": len(events),
            },
        })
