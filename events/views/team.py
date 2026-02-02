from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from events.models import Event, EventTeamMember
from core.models import CommunityMembership
from events.serializers import EventTeamMemberSerializer
from .generics import (
    user_can_manage_event_team,
    user_can_edit_event,
    user_is_system_admin,
    user_can_manage_event_attendance
)

User = get_user_model()

class EventTeamMemberListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get_event(self, event_id):
        return get_object_or_404(Event, id=event_id)

    def get(self, request, event_id):
        event = self.get_event(event_id)

        if not user_can_manage_event_team(request.user, event):
            return Response(
                {"detail": "You do not have permission to view the team for this event."},
                status=status.HTTP_403_FORBIDDEN,
            )

        team_members = (
            EventTeamMember.objects.filter(event=event, is_active=True)
            .select_related("user")
            .order_by("added_at")
        )
        serializer = EventTeamMemberSerializer(team_members, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, event_id):
        event = self.get_event(event_id)

        if not user_can_manage_event_team(request.user, event):
            return Response(
                {"detail": "You do not have permission to manage the team for this event."},
                status=status.HTTP_403_FORBIDDEN,
            )

        user_id = request.data.get("user_id")
        role = request.data.get("role")

        if not user_id or not role:
            return Response(
                {"detail": "user_id and role are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_roles = {choice[0] for choice in EventTeamMember.ROLE_CHOICES}
        if role not in valid_roles:
            return Response(
                {"detail": f"Invalid role. Valid roles: {', '.join(valid_roles)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = get_object_or_404(User, id=user_id)

        if hasattr(event, "community") and event.community is not None:
            if not CommunityMembership.objects.filter(
                community=event.community,
                user=user,
                is_active=True,
            ).exists():
                return Response(
                    {"detail": "User is not a member of this event's community."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        member, created = EventTeamMember.objects.get_or_create(
            event=event,
            user=user,
            defaults={"role": role, "is_active": True},
        )

        if not created:
            member.role = role
            member.is_active = True
            member.save(update_fields=["role", "is_active"])

        serializer = EventTeamMemberSerializer(member)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class EventTeamMemberDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_member(self, event_id, member_id):
        event = get_object_or_404(Event, id=event_id)
        member = get_object_or_404(EventTeamMember, id=member_id, event=event)
        return event, member

    def patch(self, request, event_id, member_id):
        event, member = self.get_member(event_id, member_id)

        if not user_can_manage_event_team(request.user, event):
            return Response(
                {"detail": "You do not have permission to manage the team for this event."},
                status=status.HTTP_403_FORBIDDEN,
            )

        new_role = request.data.get("role")
        if not new_role:
            return Response(
                {"detail": "role is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_roles = {choice[0] for choice in EventTeamMember.ROLE_CHOICES}
        if new_role not in valid_roles:
            return Response(
                {"detail": f"Invalid role. Valid roles: {', '.join(valid_roles)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        member.role = new_role
        member.save(update_fields=["role"])

        serializer = EventTeamMemberSerializer(member)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, event_id, member_id):
        event, member = self.get_member(event_id, member_id)

        if not user_can_manage_event_team(request.user, event):
            return Response(
                {"detail": "You do not have permission to manage the team for this event."},
                status=status.HTTP_403_FORBIDDEN,
            )

        member.is_active = False
        member.save(update_fields=["is_active"])

        return Response(status=status.HTTP_204_NO_CONTENT)


class DebugPermissionsView(APIView):
    """
    GET /api/events/debug/permissions/?event_id=<id>
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        event_id = request.query_params.get("event_id")
        if not event_id:
            return Response({"error": "event_id is required"}, status=400)

        try:
            event = Event.objects.select_related("community").get(pk=event_id)
        except Event.DoesNotExist:
            return Response({"error": "Event not found"}, status=404)

        user = request.user

        data = {
            "user": {
                "id": user.id,
                "username": user.username,
                "global_role": getattr(user, "role", None),
                "is_superuser": user.is_superuser,
            },
            "event": {
                "id": event.id,
                "title": event.title,
                "community_id": event.community_id,
                "community_name": event.community.name if event.community_id else None,
            },
            "permissions": {
                "is_system_admin": user_is_system_admin(user),
                "can_edit_event": user_can_edit_event(user, event),
                "can_manage_event_team": user_can_manage_event_team(user, event),
                "can_manage_event_attendance": user_can_manage_event_attendance(user, event),
            },
        }
        return Response(data)
