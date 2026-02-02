# ux/views/dashboard_notifications.py

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from ux.services.dashboard_notifications import (
    get_dashboard_notifications,
    mark_notifications_read,
)


class UXDashboardNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = get_dashboard_notifications(request.user)

        return Response({
            "meta": {"success": True},
            "data": data,
        })

    def post(self, request):
        ids = request.data.get("ids")
        marked = mark_notifications_read(request.user, ids=ids)

        return Response(
            {
                "meta": {"success": True},
                "data": {"marked_read": marked},
            },
            status=status.HTTP_200_OK,
        )
