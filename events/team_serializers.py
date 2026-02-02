# events/serializers.py - Add these serializers

from rest_framework import serializers
from .models import EventTeam, ParticipantTeamMember
from users.models import User


class ParticipantTeamMemberSerializer(serializers.ModelSerializer):
    """Serializer for team members"""
    username = serializers.CharField(source='user.username', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)

    class Meta:
        model = ParticipantTeamMember
        fields = ['id', 'user_id', 'username', 'joined_at', 'role']
        read_only_fields = ['id', 'joined_at']


class EventTeamSerializer(serializers.ModelSerializer):
    """Serializer for event teams with invite link generation"""
    members = ParticipantTeamMemberSerializer(many=True, read_only=True)
    creator_name = serializers.CharField(source='creator.username', read_only=True)
    current_size = serializers.IntegerField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    invite_url = serializers.CharField(read_only=True)

    class Meta:
        model = EventTeam
        fields = [
            'id', 'event', 'name', 'description', 'creator', 'creator_name',
            'invite_token', 'invite_url', 'max_size', 'current_size', 'is_full',
            'is_locked', 'skills_needed', 'members', 'created_at'
        ]
        read_only_fields = ['id', 'creator', 'invite_token', 'created_at']

    def create(self, validated_data):
        # Set creator from request user
        validated_data['creator'] = self.context['request'].user
        team = super().create(validated_data)

        # Lazy import to avoid circular dependency
        from .models import EventRegistration

        # Auto-add creator as team leader
        ParticipantTeamMember.objects.create(
            team=team,
            user=team.creator,
            role='leader',
            registration=EventRegistration.objects.filter(
                user=team.creator,
                event=team.event
            ).first()
        )

        return team


class TeamJoinSerializer(serializers.Serializer):
    """Serializer for joining a team via invite token"""
    invite_token = serializers.UUIDField()

    def validate_invite_token(self, value):
        try:
            team = EventTeam.objects.get(invite_token=value)
        except EventTeam.DoesNotExist:
            raise serializers.ValidationError("Invalid invite token")

        if team.is_locked:
            raise serializers.ValidationError("This team is no longer accepting members")

        if team.is_full:
            raise serializers.ValidationError("This team is full")

        return value

    def save(self):
        # Lazy import to avoid circular dependency
        from .models import EventRegistration

        user = self.context['request'].user
        team = EventTeam.objects.get(invite_token=self.validated_data['invite_token'])

        # Check if already a member
        if ParticipantTeamMember.objects.filter(team=team, user=user).exists():
            raise serializers.ValidationError("You are already a member of this team")

        # Get or create registration
        registration, created = EventRegistration.objects.get_or_create(
            user=user,
            event=team.event,
            defaults={
                'status': EventRegistration.STATUS_APPROVED,
                'payment_status': EventRegistration.PAYMENT_SKIPPED
            }
        )

        # Add to team
        member = ParticipantTeamMember.objects.create(
            team=team,
            user=user,
            registration=registration,
            role='member'
        )

        return member


class ProfileSyncSerializer(serializers.ModelSerializer):
    """Serializer for user profile data used in event registration auto-fill"""

    class Meta:
        model = User
        fields = [
            'institution', 'graduation_year', 'degree', 'skills', 'experience_level',
            'github_url', 'linkedin_url', 'portfolio_url', 'resume_url',
            'dietary_preferences', 'tshirt_size',
            'emergency_contact_name', 'emergency_contact_phone',
            'allow_profile_autofill'
        ]
