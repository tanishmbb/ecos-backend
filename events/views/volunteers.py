from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone

from events.models import Event, EventVolunteer
from events.serializers import EventVolunteerSerializer

class VolunteerForEventView(APIView):
    """
    POST: Participant volunteers for an event.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, event_id):
        event = get_object_or_404(Event, id=event_id)

        # Check if already volunteered
        if EventVolunteer.objects.filter(event=event, user=request.user).exists():
            return Response({"error": "You have already volunteered for this event."}, status=400)

        # Check if event accepts volunteers? (Assuming validation or just open for now, feature flag usually)

        role = request.data.get("role", "Helper")

        volunteer = EventVolunteer.objects.create(
            event=event,
            user=request.user,
            role=role,
            status=EventVolunteer.STATUS_PENDING
        )

        return Response(EventVolunteerSerializer(volunteer).data, status=201)


class EventVolunteerListView(APIView):
    """
    GET: List all volunteers for an event (Organizer only).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id):
        event = get_object_or_404(Event, id=event_id)

        # Permission: Must be community organizer or event organizer
        # Simplified check (reusing logic from core or implementing local)
        can_manage = (request.user == event.organizer)
        if not can_manage:
            # Check community role
            from core.models import CommunityMembership
            mem = CommunityMembership.objects.filter(community=event.community, user=request.user, is_active=True).first()
            if mem and mem.role in [CommunityMembership.ROLE_OWNER, CommunityMembership.ROLE_ORGANIZER, CommunityMembership.ROLE_ADMIN]:
                can_manage = True

        if not can_manage:
            return Response({"error": "Unauthorized"}, status=403)

        volunteers = EventVolunteer.objects.filter(event=event).order_by("-created_at")
        serializer = EventVolunteerSerializer(volunteers, many=True)
        return Response(serializer.data)


class EventVolunteerDetailView(APIView):
    """
    PATCH: Approve/Reject/Verify/Complete a volunteer (Organizer only).
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, event_id, pk):
        event = get_object_or_404(Event, id=event_id)

        # Permission check
        can_manage = (request.user == event.organizer)
        if not can_manage:
            from core.models import CommunityMembership
            mem = CommunityMembership.objects.filter(community=event.community, user=request.user, is_active=True).first()
            if mem and mem.role in [CommunityMembership.ROLE_OWNER, CommunityMembership.ROLE_ORGANIZER, CommunityMembership.ROLE_ADMIN]:
                can_manage = True

        if not can_manage:
            return Response({"error": "Unauthorized"}, status=403)

        volunteer = get_object_or_404(EventVolunteer, id=pk, event=event)

        status_val = request.data.get("status")
        note = request.data.get("note")

        if status_val:
            if status_val not in dict(EventVolunteer.STATUS_CHOICES):
                return Response({"error": "Invalid status"}, status=400)
            volunteer.status = status_val

            # If completed, mark verified_by
            if status_val == EventVolunteer.STATUS_COMPLETED:
                volunteer.verified_by = request.user

                # Signal: Create/Generate Accomplishment
                # For now, we just save. Accomplishment generation is Phase 2.5

        if note is not None:
            volunteer.note = note

        volunteer.save()
        return Response(EventVolunteerSerializer(volunteer).data)
