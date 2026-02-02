# events/views/teams.py - Team Formation API Views

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from events.models import Event, EventTeam, ParticipantTeamMember
from events.team_serializers import (
    EventTeamSerializer,
    TeamJoinSerializer,
    ParticipantTeamMemberSerializer
)
from core.services import ActivityService
from core.constants import ACTIVITY_EVENT_REGISTERED


class EventTeamViewSet(viewsets.ModelViewSet):
    """
    API for creating and managing event teams

    Competitive Feature: Team invite links (parity with devnovate)
    Trust Advantage: Full audit trail via DomainActivity
    """
    serializer_class = EventTeamSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Filter by event if provided
        event_id = self.request.query_params.get('event')
        if event_id:
            return EventTeam.objects.filter(event_id=event_id).prefetch_related('members')
        return EventTeam.objects.none()

    def perform_create(self, serializer):
        team = serializer.save()

        # Log team creation in activity ledger
        ActivityService.log_activity(
            actor=self.request.user,
            verb='team.created',
            community=team.event.community,
            metadata={
                'team_id': team.id,
                'team_name': team.name,
                'event_id': team.event.id,
                'event_title': team.event.title
            }
        )

    @action(detail=False, methods=['post'], url_path='join')
    def join_team(self, request):
        """
        Join a team via invite token

        POST /api/events/teams/join/
        Body: {"invite_token": "uuid"}

        Auto-registers user for event if not already registered
        """
        serializer = TeamJoinSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        member = serializer.save()

        # Log team join
        ActivityService.log_activity(
            actor=request.user,
            verb='team.joined',
            community=member.team.event.community,
            metadata={
                'team_id': member.team.id,
                'team_name': member.team.name,
                'event_id': member.team.event.id,
                'event_title': member.team.event.title
            }
        )

        return Response(
            ParticipantTeamMemberSerializer(member).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], url_path='lock')
    def lock_team(self, request, pk=None):
        """Lock team to prevent new members (team leader only)"""
        team = self.get_object()

        # Verify user is team leader
        member = ParticipantTeamMember.objects.filter(
            team=team,
            user=request.user,
            role='leader'
        ).first()

        if not member:
            return Response(
                {'error': 'Only team leaders can lock the team'},
                status=status.HTTP_403_FORBIDDEN
            )

        team.is_locked = True
        team.save()

        return Response({'status': 'Team locked'})

    @action(detail=True, methods=['delete'], url_path='leave')
    def leave_team(self, request, pk=None):
        """Leave a team (members only, leaders cannot leave)"""
        team = self.get_object()

        member = ParticipantTeamMember.objects.filter(
            team=team,
            user=request.user
        ).first()

        if not member:
            return Response(
                {'error': 'You are not a member of this team'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if member.role == 'leader':
            return Response(
                {'error': 'Team leaders cannot leave. Transfer leadership or delete the team.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        member.delete()

        # Log team leave
        ActivityService.log_activity(
            actor=request.user,
            verb='team.left',
            community=team.event.community,
            metadata={
                'team_id': team.id,
                'team_name': team.name
            }
        )

        return Response(status=status.HTTP_204_NO_CONTENT)
