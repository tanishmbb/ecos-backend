# ux/views/dashboard_communities.py

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ux.services.dashboard_communities import get_dashboard_communities


class UXDashboardCommunitiesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = get_dashboard_communities(request.user)

        return Response({
            "meta": {"success": True},
            "data": data,
        })
