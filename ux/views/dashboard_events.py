# ux/views/dashboard_events.py

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ux.services.dashboard_events import get_dashboard_events


class UXDashboardEventsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        events = get_dashboard_events(request.user)

        return Response({
            "meta": {"success": True},
            "data": events,
        })
