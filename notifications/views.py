from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from .models import Notification
from .serializers import NotificationSerializer


class MyNotificationsView(APIView):
    """
    GET /api/core/notifications/me/
    GET /api/core/notifications/me/?unread=true
    POST /api/core/notifications/me/mark-read/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        unread_only = request.query_params.get("unread")
        qs = Notification.objects.filter(user=request.user)

        if unread_only and unread_only.lower() in ("1", "true", "yes"):
            qs = qs.filter(is_read=False)

        serializer = NotificationSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        """
        Mark notifications as read.

        Body:
        {
          "ids": [1, 2, 3]   # or omit/empty to mark all as read
        }
        """
        ids = request.data.get("ids")
        qs = Notification.objects.filter(user=request.user, is_read=False)

        if ids:
            qs = qs.filter(id__in=ids)

        updated = qs.update(is_read=True)
        return Response({"marked_read": updated}, status=status.HTTP_200_OK)
