from rest_framework import serializers
from .models import FeedItem, Announcement, FeedLike, FeedComment
from events.serializers import EventSerializer
from events.models import Certificate
from rest_framework import serializers
from .models import Announcement, FeedItem, Community, CommunityMembership, CommunityInvite, DomainActivity


class AnnouncementSerializer(serializers.ModelSerializer):
    organizer_name = serializers.CharField(source='organizer.username', read_only=True)
    event_details = EventSerializer(source='event', read_only=True)

    class Meta:
        model = Announcement
        fields = [
            'id',
            'title',
            'message',
            'created_at',
            'organizer_name',
            'event',            # INTEGER ID
            'event_details'     # FULL EVENT DATA
        ]




class FeedLikeSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = FeedLike
        fields = ["id", "user", "username", "created_at"]


class FeedCommentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    user_avatar = serializers.CharField(source="user.profile_picture", read_only=True)

    class Meta:
        model = FeedComment
        fields = ["id", "user", "username", "user_avatar", "text", "created_at"]


class DomainActivitySerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.username', read_only=True)
    community_name = serializers.CharField(source='community.name', read_only=True)

    class Meta:
        model = DomainActivity
        fields = [
            'id',
            'actor_name',
            'verb',
            'community',
            'community_name',
            'metadata',
            'timestamp',
            'visibility'
        ]


class FeedSerializer(serializers.ModelSerializer):
    event = EventSerializer(read_only=True)
    announcement = AnnouncementSerializer(read_only=True)
    activity = DomainActivitySerializer(read_only=True)

    # 🔹 Interaction Data
    likes_count = serializers.IntegerField(source="likes.count", read_only=True)
    comments_count = serializers.IntegerField(source="comments.count", read_only=True)
    is_liked = serializers.SerializerMethodField()
    comments = FeedCommentSerializer(many=True, read_only=True)

    class Meta:
        model = FeedItem
        fields = [
            'id',
            'type',
            'created_at',
            'event',
            'announcement',
            'activity',
            'likes_count',
            'comments_count',
            'is_liked',
            'comments'
        ]

    def get_is_liked(self, obj) -> bool:
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False
class CommunityInviteSerializer(serializers.ModelSerializer):
    invite_url = serializers.SerializerMethodField()

    class Meta:
        model = CommunityInvite
        fields = [
            "id",
            "community",
            "token",
            "role",
            "max_uses",
            "used_count",
            "expires_at",
            "is_active",
            "created_at",
            "invite_url",
        ]
        read_only_fields = [
            "id",
            "community",
            "token",
            "used_count",
            "is_active",
            "created_at",
            "invite_url",
        ]

    def get_invite_url(self, obj):
        """
        Returns a URL frontend can use, e.g. /join/<token>/.
        You can change the pattern later to match your React routes.
        """
        request = self.context.get("request")
        path = f"/communities/join/{obj.token}/"
        if request is not None:
            return request.build_absolute_uri(path)
        return path
class CommunityMembershipSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = CommunityMembership
        fields = [
            "id",
            "community",
            "user_id",
            "username",
            "role",
            "is_active",
            "is_default",
            "last_active_at",
            "joined_at",
        ]
        
        read_only_fields = [
            "id",
            "community",
            "user_id",
            "username",
            "is_default",
            "last_active_at",
            "joined_at",
        ]


class MembershipApplicationSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    user_avatar = serializers.CharField(source='user.profile_picture', read_only=True)
    reviewer_name = serializers.CharField(source='reviewed_by.username', read_only=True)

    class Meta:
        from .models import MembershipApplication
        model = MembershipApplication
        fields = [
            'id', 'user', 'user_name', 'user_avatar',
            'community', 'intent', 'skills',
            'status', 'reviewed_by', 'reviewer_name', 'reviewed_at',
            'created_at'
        ]
        read_only_fields = [
            'id', 'user', 'community', 'status', 'reviewed_by', 'reviewed_at', 'created_at'
        ]

class CommunityToDoSerializer(serializers.ModelSerializer):
    assigned_username = serializers.CharField(source='assigned_to.username', read_only=True)
    creator_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        from .models import CommunityToDo
        model = CommunityToDo
        fields = [
            'id', 'community', 'title', 'description',
            'status', 'priority', 'assigned_to', 'assigned_username',
            'created_by', 'creator_username', 'due_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'community', 'created_by', 'created_at', 'updated_at']

class UserAccomplishmentSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import UserAccomplishment
        model = UserAccomplishment
        fields = '__all__'
