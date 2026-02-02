from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q

from core.models import Community, CommunityMembership
from events.models import Event, EventRegistration, EventFeedback, EventTeamMember
from events import serializers as event_serializers
from events.serializers import EventSerializer, CertificateSerializer
from events.throttles import CommunityEventCreateThrottle
from .generics import (
    user_is_system_admin,
    user_can_edit_event,
    get_active_community_id_for_user,
    api_error
)

class EventListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [CommunityEventCreateThrottle]

    def get(self, request):
        qs = Event.objects.all()
        user = request.user
        qs = qs.filter(status=Event.STATUS_APPROVED)

        # 🔹 Privacy Filter: Only show public communities OR communities where user is a member
        # (Events without a community are assumed public/system-level)
        member_community_ids = []
        if request.user.is_authenticated:
            member_community_ids = CommunityMembership.objects.filter(
                user=request.user, is_active=True
            ).values_list("community_id", flat=True)

        qs = qs.filter(
             Q(community__isnull=True) |
             Q(community__is_private=False) |
             Q(community__id__in=member_community_ids)
        ).distinct()

        # Filters...
        community_id = request.query_params.get("community_id") or request.query_params.get("community")
        if community_id:
            qs = qs.filter(community_id=community_id)

        status_param = request.query_params.get("status")
        now = timezone.now()
        if status_param == "upcoming":
            qs = qs.filter(start_time__gte=now)
        elif status_param == "past":
            qs = qs.filter(end_time__lt=now)
        elif status_param == "ongoing":
            qs = qs.filter(start_time__lte=now, end_time__gte=now)

        mine_param = request.query_params.get("mine")
        if mine_param and mine_param.lower() in ("1", "true", "yes"):
            qs = qs.filter(
                Q(organizer=user) |
                Q(eventregistration__user=user) |
                Q(team_members__user=user, team_members__is_active=True)
            ).distinct()

        public_param = request.query_params.get("public")
        if public_param and public_param.lower() in ("1", "true", "yes"):
            qs = qs.filter(is_public=True)

        search = request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search)
            )

        ordering = request.query_params.get("ordering")
        allowed_ordering = {"start_time", "-start_time", "created_at", "-created_at"}
        if ordering in allowed_ordering:
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by("-start_time")

        # Get total count before pagination for proper pagination response
        total_count = qs.count()

        # Pagination
        limit = request.query_params.get("limit")
        offset = request.query_params.get("offset")

        try:
            limit_val = int(limit) if limit is not None else 50  # Default page size
            offset_val = int(offset) if offset is not None else 0
        except ValueError:
            return Response({"error": "Invalid pagination params"}, status=400)

        limit_val = max(1, min(limit_val, 100))  # Cap at 100
        offset_val = max(0, offset_val)

        # Optimize queries: select_related for FK, annotate for counts
        from django.db.models import Count, Sum, Q as QFilter

        qs = qs.select_related('organizer', 'community').annotate(
            _annotated_attendees_count=Count(
                'eventregistration',
                filter=QFilter(eventregistration__status__in=['approved', 'attended'])
            )
        )

        # Apply pagination
        qs = qs[offset_val : offset_val + limit_val]

        serializer = EventSerializer(qs, many=True, context={'request': request})
        return Response({
            "count": total_count,
            "results": serializer.data,
            "limit": limit_val,
            "offset": offset_val,
        })

    def post(self, request):
        serializer = EventSerializer(
            data=request.data,
            context={"request": request},
        )
        if not serializer.is_valid():
            with open('d:/cos-backend/debug_event_create.txt', 'w') as f:
                f.write(f"User: {request.user}\n")
                f.write(f"Auth: {request.auth}\n")
                f.write(f"Data: {request.data}\n")
                f.write(f"Errors: {serializer.errors}\n")
            return Response(serializer.errors, status=400)


        community = None
        community_id = serializer.validated_data.get("community_id")

        if community_id is not None:
            community = get_object_or_404(Community, pk=community_id, is_active=True)

            membership = CommunityMembership.objects.filter(
                community=community,
                user=request.user,
                is_active=True,
            ).first()

            if not membership or membership.role not in [
                CommunityMembership.ROLE_OWNER,
                CommunityMembership.ROLE_ORGANIZER,
                CommunityMembership.ROLE_ADMIN,
            ]:
                return Response(
                    {"error": "You are not allowed to create events in this community."},
                    status=403,
                )

        if user_is_system_admin(request.user):
            initial_status = Event.STATUS_APPROVED
        elif community_id and membership and membership.role in [
            CommunityMembership.ROLE_OWNER,
            CommunityMembership.ROLE_ADMIN,
        ]:
            initial_status = Event.STATUS_APPROVED
        else:
            initial_status = Event.STATUS_PENDING

        event = serializer.save(
            organizer=request.user,
            community=community,
            status=initial_status,
        )

        return Response(EventSerializer(event).data, status=201)


class EventApprovalView(APIView):
    """
    POST /api/events/events/<event_id>/approve/
    POST /api/events/events/<event_id>/reject/
    """
    authentication_classes = [JWTAuthentication, SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, event_id, action):
        try:
            event = Event.objects.select_related("community").get(pk=event_id)
        except Event.DoesNotExist:
            return Response({"error": "Event not found"}, status=404)

        user = request.user

        if user_is_system_admin(user):
            can_manage = True
        else:
            if not event.community_id:
                return Response({"error": "Event has no community"}, status=400)

            membership = CommunityMembership.objects.filter(
                community=event.community,
                user=user,
                is_active=True,
            ).first()

            can_manage = membership and membership.role in [
                CommunityMembership.ROLE_OWNER,
                CommunityMembership.ROLE_ADMIN,
            ]

        if not can_manage:
            return Response({"error": "Not allowed"}, status=403)

        requested_status = request.data.get("status")
        if action == "approve":
            new_status = Event.STATUS_APPROVED
        elif action == "reject":
            new_status = Event.STATUS_REJECTED
        else:
            return Response({"error": "Invalid action"}, status=400)

        if requested_status in [Event.STATUS_APPROVED, Event.STATUS_REJECTED, Event.STATUS_PENDING]:
            new_status = requested_status

        event.status = new_status
        event.save(update_fields=["status"])

        return Response({"event_id": event.id, "new_status": event.status}, status=200)


class PublicEventDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, event_id):
        event = get_object_or_404(
            Event,
            id=event_id,
            is_public=True,
            status=Event.STATUS_APPROVED,
        )

        serializer = EventSerializer(event, context={"request": request})
        return Response(serializer.data)


class EventDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Event.objects.get(pk=pk)
        except Event.DoesNotExist:
            return None

    def get(self, request, pk):
        event = self.get_object(pk)
        if event is None:
            return api_error("Event not found", status.HTTP_404_NOT_FOUND)

        serializer = EventSerializer(event)
        return Response(serializer.data)

    def put(self, request, pk):
        event = self.get_object(pk)
        if event is None:
            return api_error("Event not found", status.HTTP_404_NOT_FOUND)

        if not user_can_edit_event(request.user, event):
            return api_error("You do not have permission to edit this event.", status.HTTP_403_FORBIDDEN)

        serializer = EventSerializer(event, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        event = self.get_object(pk)
        if event is None:
            return api_error("Event not found", status.HTTP_404_NOT_FOUND)

        if not user_can_edit_event(request.user, event):
            return api_error("You do not have permission to delete this event.", status.HTTP_403_FORBIDDEN)

        event.delete()
        return Response({"message": "Event deleted"})


class MyUpcomingEventsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()

        regs = (
            EventRegistration.objects
            .select_related("event", "event__organizer", "attendance", "certificate")
            .filter(user=request.user, event__end_time__gte=now)
        )

        community_id = request.query_params.get("community_id")

        if community_id:
            regs = regs.filter(event__community_id=community_id)

        regs = regs.order_by("event__start_time")

        event_ids = [reg.event_id for reg in regs]
        feedback_map = {
            fb.event_id: fb
            for fb in EventFeedback.objects.filter(event_id__in=event_ids, user=request.user)
        }

        enriched = []
        for reg in regs:
            event = reg.event
            attendance = getattr(reg, "attendance", None)
            certificate = getattr(reg, "certificate", None)
            feedback = feedback_map.get(event.id)

            event_data = event_serializers.EventSerializer(event).data
            event_data["registration_id"] = reg.id
            event_data["attendance"] = {
                "checked_in": bool(attendance and attendance.check_in),
                "checked_out": bool(attendance and attendance.check_out),
                "qr_code": str(attendance.qr_code) if attendance else None,
            }

            cert_data = None
            if certificate:
                cert_data = CertificateSerializer(certificate, context={"request": request}, many=False).data
            event_data["certificate"] = cert_data

            event_data["feedback"] = {
                "given": feedback is not None,
                "rating": feedback.rating if feedback else None,
                "comment": feedback.comment if feedback else None,
            }
            event_data["can_give_feedback"] = event.start_time <= now and feedback is None

            enriched.append(event_data)

        return Response(enriched, status=status.HTTP_200_OK)


class MyPastEventsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        regs = (
            EventRegistration.objects
            .select_related("event", "event__organizer", "attendance", "certificate")
            .filter(user=request.user, event__start_time__lt=now)
        )

        community_id = request.query_params.get("community_id")

        if community_id:
            regs = regs.filter(event__community_id=community_id)

        regs = regs.order_by("-event__start_time")

        event_ids = [reg.event_id for reg in regs]
        feedback_map = {
            fb.event_id: fb
            for fb in EventFeedback.objects.filter(event_id__in=event_ids, user=request.user)
        }

        enriched = []
        for reg in regs:
            event = reg.event
            attendance = getattr(reg, "attendance", None)
            certificate = getattr(reg, "certificate", None)
            feedback = feedback_map.get(event.id)

            event_data = event_serializers.EventSerializer(event).data
            event_data["registration_id"] = reg.id
            event_data["attendance"] = {
                "checked_in": bool(attendance and attendance.check_in),
                "checked_out": bool(attendance and attendance.check_out),
            }

            if certificate:
                event_data["certificate"] = CertificateSerializer(
                    certificate, context={"request": request}, many=False
                ).data
            else:
                event_data["certificate"] = None

            event_data["feedback"] = {
                "given": feedback is not None,
                "rating": feedback.rating if feedback else None,
                "comment": feedback.comment if feedback else None,
            }
            event_data["can_give_feedback"] = feedback is None

            enriched.append(event_data)

        return Response(enriched, status=status.HTTP_200_OK)


class MyDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        now = timezone.now()

        base_events = Event.objects.filter(
            Q(organizer=user)
            | Q(eventregistration__user=user)
            | Q(team_members__user=user, team_members__is_active=True)
        ).distinct()

        upcoming_qs = base_events.filter(start_time__gte=now)
        past_qs = base_events.filter(end_time__lt=now)

        upcoming_events = upcoming_qs.order_by("start_time")[:10]
        past_events = past_qs.order_by("-start_time")[:10]

        upcoming_data = EventSerializer(upcoming_events, many=True).data
        past_data = EventSerializer(past_events, many=True).data

        return Response({
            "upcoming_total": upcoming_qs.count(),
            "past_total": past_qs.count(),
            "upcoming_events": upcoming_data,
            "past_events": past_data,
        })


class OrganizerDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        now = timezone.now()

        if user_is_system_admin(user):
            managed_events = Event.objects.all()
        else:
            managed_events = Event.objects.filter(
                Q(organizer=user)
                | Q(
                    community__memberships__user=user,
                    community__memberships__role__in=[
                        CommunityMembership.ROLE_OWNER,
                        CommunityMembership.ROLE_ORGANIZER,
                        CommunityMembership.ROLE_ADMIN,
                    ],
                    community__memberships__is_active=True,
                )
                | Q(
                    team_members__user=user,
                    team_members__is_active=True,
                    team_members__role__in=[
                        EventTeamMember.ROLE_HOST,
                        EventTeamMember.ROLE_CO_HOST,
                    ],
                )
            ).distinct()

        upcoming_qs = managed_events.filter(start_time__gte=now)
        past_qs = managed_events.filter(end_time__lt=now)

        upcoming_events = upcoming_qs.order_by("start_time")[:20]
        past_events = past_qs.order_by("-start_time")[:20]

        return Response({
            "managed_total": managed_events.count(),
            "upcoming_total": upcoming_qs.count(),
            "past_total": past_qs.count(),
            "upcoming_events": EventSerializer(upcoming_events, many=True).data,
            "past_events": EventSerializer(past_events, many=True).data,
        })
