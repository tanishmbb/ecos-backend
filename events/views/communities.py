from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.contrib.auth import get_user_model

from core.models import Community, CommunityMembership
from events.models import Event, EventRegistration, Certificate
from events import serializers as event_serializers
from events.throttles import CommunityEventCreateThrottle
from .generics import get_active_community_id_for_user

User = get_user_model()

class CommunityListCreateView(APIView):
    """
    GET  /communities/   → list communities user belongs to
    POST /communities/   → create community + assign owner role
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = (
            CommunityMembership.objects
            .select_related("community")
            .filter(user=request.user, is_active=True)
        )
        communities = [m.community for m in memberships]

        serializer = event_serializers.CommunitySerializer(communities, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = event_serializers.CommunitySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        community = serializer.save(created_by=request.user)

        CommunityMembership.objects.create(
            community=community,
            user=request.user,
            role=CommunityMembership.ROLE_OWNER,
            is_active=True,
        )

        return Response(
            event_serializers.CommunitySerializer(community).data,
            status=201,
        )


class CommunityMembersView(APIView):
    """
    GET /communities/<id>/members/ → list members (requires organizer/admin/owner)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, community_id):
        community = get_object_or_404(Community, pk=community_id)

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
            return Response({"error": "Not allowed"}, status=403)

        members = (
            CommunityMembership.objects
            .select_related("user", "community")
            .filter(community=community, is_active=True)
            .order_by("user__username")
        )

        serializer = event_serializers.CommunityMembershipSerializer(members, many=True)
        return Response(serializer.data)


class AddCommunityMemberView(APIView):
    """
    POST /communities/<id>/members/add/
        Body → { user_id, role }
    Only owner can add/update member
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, community_id):
        community = get_object_or_404(Community, pk=community_id)

        owner_membership = CommunityMembership.objects.filter(
            community=community,
            user=request.user,
            role=CommunityMembership.ROLE_OWNER,
            is_active=True,
        ).first()

        if not owner_membership:
            return Response({"error": "Only owner can add members"}, status=403)

        user_id = request.data.get("user_id")
        role = request.data.get("role", CommunityMembership.ROLE_MEMBER)

        if not user_id:
            return Response({"error": "user_id is required"}, status=400)

        if role not in dict(CommunityMembership.ROLE_CHOICES):
            return Response({"error": "Invalid role"}, status=400)

        target_user = get_object_or_404(User, pk=user_id)

        membership, created = CommunityMembership.objects.get_or_create(
            community=community,
            user=target_user,
            defaults={"role": role, "is_active": True},
        )

        if not created:
            membership.role = role
            membership.is_active = True
            membership.save(update_fields=["role", "is_active"])

        serializer = event_serializers.CommunityMembershipSerializer(membership)
        return Response(serializer.data, status=201 if created else 200)


class PublicCommunityEventsView(APIView):
    """
    GET /api/events/public/<community_slug>/

    Public endpoint — no auth required.

    Returns:
    - community branding
    - list of public events (future + ongoing)
    """
    permission_classes = [AllowAny]

    def get(self, request, community_slug):
        # 1. Resolve community by slug
        community = get_object_or_404(Community, slug=community_slug, is_active=True)

        now = timezone.now()

        # 2. Fetch upcoming / ongoing public events
        events_qs = (
            Event.objects
            .filter(
                community=community,
                is_public=True,
                status=Event.STATUS_APPROVED,
            )
            .order_by("start_time")
        )

        # 🔹 Privacy Logic: Hide events if community is private and user is not a member
        if community.is_private:
            is_member = False
            if request.user.is_authenticated:
                is_member = CommunityMembership.objects.filter(
                    community=community,
                    user=request.user,
                    is_active=True
                ).exists()

            if not is_member:
                events_qs = events_qs.none()

        # TODO: Handle private community logic here later

        event_data = event_serializers.EventSerializer(
            events_qs,
            many=True,
            context={"request": request},
        ).data

        # 3. Branding info
        comm_data = event_serializers.CommunitySerializer(
            community,
            context={"request": request},
        ).data

        return Response(
            {
                "community": {
                    "id": community.id,
                    "name": community.name,
                    "slug": community.slug,
                    "description": community.description,
                    "primary_color": comm_data.get("primary_color"),
                    "logo_url": comm_data.get("logo_url"),
                    "certificate_template_url": comm_data.get("certificate_template_url"),
                },
                "events": event_data,
                "count": len(event_data),
            },
            status=status.HTTP_200_OK,
        )


class PublicCommunityListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        qs = Community.objects.filter(is_active=True).order_by("name")
        serializer = event_serializers.CommunitySerializer(
            qs,
            many=True,
            context={"request": request}
        )
        return Response(serializer.data)


from events.analytics import get_community_stats

class CommunityOverviewView(APIView):
    """
    GET /api/v1/events/communities/<community_id>/overview/
    Returns community info + aggregated stats.
    Only owner / admin / organizer in that community can access.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [CommunityEventCreateThrottle]
    def get(self, request, community_id):
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
            return Response({"error": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        community_data = event_serializers.CommunitySerializer(community).data
        stats = get_community_stats(community)

        return Response(
            {
                "community": community_data,
                "stats": stats,
            },
            status=status.HTTP_200_OK,
        )


class CommunityEventsView(APIView):
    """
    GET /api/v1/events/communities/<community_id>/events/
    List all events in this community.
    Only members of the community can view; non-members get 403.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, community_id):
        community = get_object_or_404(Community, pk=community_id, is_active=True)

        membership_exists = CommunityMembership.objects.filter(
            community=community,
            user=request.user,
            is_active=True,
        ).exists()

        if not membership_exists:
            return Response({"error": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        events_qs = (
            Event.objects
            .filter(community=community)
            .order_by("-start_time")
        )

        serializer = event_serializers.EventSerializer(events_qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MyCommunitiesView(APIView):
    """
    GET /api/v1/events/me/communities/
    List communities the current user belongs to (memberships),
    including is_default flag.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = (
            CommunityMembership.objects
            .select_related("community")
            .filter(user=request.user, is_active=True)
            .order_by("community__name")
        )
        serializer = event_serializers.CommunityMembershipSerializer(memberships, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SetActiveCommunityView(APIView):
    """
    POST /api/v1/events/me/communities/<community_id>/set_active/
    Sets this community as the user's active/default community.
    Requires the user to be a member of that community.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, community_id):
        community = get_object_or_404(Community, pk=community_id, is_active=True)

        membership = CommunityMembership.objects.filter(
            community=community,
            user=request.user,
            is_active=True,
        ).first()

        if not membership:
            return Response(
                {"error": "You are not a member of this community."},
                status=status.HTTP_403_FORBIDDEN,
            )

        (
            CommunityMembership.objects
            .filter(user=request.user, is_active=True, is_default=True)
            .exclude(pk=membership.pk)
            .update(is_default=False)
        )

        membership.is_default = True
        membership.last_active_at = timezone.now()
        membership.save(update_fields=["is_default", "last_active_at"])

        serializer = event_serializers.CommunityMembershipSerializer(membership)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ActiveContextView(APIView):
    """
    GET /api/events/me/active-context/

    Returns a compact snapshot for frontend UI:
    - active community details + branding
    - membership info
    - basic stats (upcoming/past events, certificates)
    - useful shortcut URLs (for frontend to consume or ignore)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        now = timezone.now()

        # 1) Determine active community id
        #    priority: query param > header > stored default
        community_id = (
            request.query_params.get("community_id")
            or request.headers.get("X-Community-ID")
        )
        if not community_id:
            community_id = get_active_community_id_for_user(user)

        active_membership = None
        active_community = None

        if community_id:
            active_membership = (
                CommunityMembership.objects
                .select_related("community")
                .filter(
                    user=user,
                    community_id=community_id,
                    is_active=True,
                )
                .first()
            )
            if active_membership:
                active_community = active_membership.community

        # 2) Serialize community + membership
        community_data = None
        membership_data = None

        if active_community:
            community_data = event_serializers.CommunitySerializer(
                active_community,
                context={"request": request},
            ).data

        if active_membership:
            membership_data = event_serializers.CommunityMembershipSerializer(active_membership).data

        # 3) Compute basic stats scoped to active community (or global if none)
        regs = EventRegistration.objects.filter(user=user)
        certs = Certificate.objects.filter(registration__user=user)

        if community_id and active_community:
            regs = regs.filter(event__community_id=active_community.id)
            certs = certs.filter(registration__event__community_id=active_community.id)

        upcoming_count = regs.filter(event__end_time__gte=now).count()
        past_count = regs.filter(event__start_time__lt=now).count()
        cert_count = certs.count()

        # 4) Suggest useful API shortcuts for frontend
        cid_param = f"?community_id={active_community.id}" if active_community else ""

        shortcuts = [
            {
                "name": "My upcoming events",
                "type": "list",
                "endpoint": f"/api/events/me/upcoming/{cid_param}",
            },
            {
                "name": "My past events",
                "type": "list",
                "endpoint": f"/api/events/me/past/{cid_param}",
            },
            {
                "name": "My certificates",
                "type": "list",
                "endpoint": f"/api/events/me/certificates/{cid_param}",
            },
            {
                "name": "My announcements",
                "type": "list",
                "endpoint": f"/api/events/me/announcements/{cid_param}",
            },
            {
                "name": "My communities",
                "type": "list",
                "endpoint": "/api/events/me/communities/",
            },
        ]

        return Response(
            {
                "active_community": community_data,
                "membership": membership_data,
                "stats": {
                    "upcoming_events": upcoming_count,
                    "past_events": past_count,
                    "certificates": cert_count,
                },
                "shortcuts": shortcuts,
            }
        )
