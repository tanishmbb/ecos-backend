# ux/views/dashboard.py

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ux.services.dashboard import get_dashboard_summary


class UXDashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        stats = get_dashboard_summary(request.user)

        return Response({
            "meta": {"success": True},
            "data": {
                "stats": stats
            }
        })
