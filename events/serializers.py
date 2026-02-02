from rest_framework import serializers
from core.models import Community, CommunityMembership
from gamification.models import UserCommunityStats
from .models import (
    Event,
    EventRegistration,
    EventAttendance,
    Certificate,
    Announcement,
    EventFeedback,
    EventTeamMember,
)
from .sanitizers import (
    sanitize_title,
    sanitize_description,
    validate_capacity,
    validate_price,
    validate_guests,
    ValidationError as SanitizationError,
)


# -----------------------------------------
# COMMUNITY SERIALIZER (branding aware)
# -----------------------------------------
class CommunitySerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    certificate_template_url = serializers.SerializerMethodField()

    class Meta:
        model = Community
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "logo",
            "logo_url",
            "primary_color",
            "certificate_template",
            "certificate_template_url",
            "is_private",
            "is_active",
            "created_at",
            "member_count",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "description",
            "logo_url",
            "certificate_template_url",
            "member_count",
        ]

    member_count = serializers.IntegerField(source="memberships.count", read_only=True)

    def get_logo_url(self, obj):
        request = self.context.get("request")
        if obj.logo and hasattr(obj.logo, "url"):
            url = obj.logo.url
            return request.build_absolute_uri(url) if request else url
        return None

    def get_certificate_template_url(self, obj):
        request = self.context.get("request")
        if obj.certificate_template and hasattr(obj.certificate_template, "url"):
            url = obj.certificate_template.url
            return request.build_absolute_uri(url) if request else url
        return None


# -----------------------------------------
# EVENT SERIALIZER — includes branding
# -----------------------------------------
# ... (rest of imports unchanged)



class EventSerializer(serializers.ModelSerializer):
    organizer_name = serializers.CharField(
        source="organizer.username", read_only=True
    )
    # For multi-community
    community_id = serializers.IntegerField(
        write_only=True, required=False, allow_null=True
    )
    community_name = serializers.CharField(
        source="community.name", read_only=True
    )

    is_registered = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id",
            "organizer",
            "organizer_name",
            "title",
            "status",
            "description",
            "start_time",
            "end_time",
            "capacity",
            "venue",
            "banner",
            "is_public",

            # New Event OS Fields
            "event_type",
            "is_paid",
            "price",
            "currency",
            "waitlist_enabled",
            "location_lat",
            "location_lng",

            "created_at",
            "community",
            "community_id",
            "community_name",
            "community_slug",
            "is_registered",
            "attendees_count",
            "location",
        ]
        read_only_fields = [
            "id",
            "organizer",
            "created_at",
            "community",
            "community_name",
            "community_slug",
            "is_registered",
            "attendees_count",
            "location",
        ]

    community_slug = serializers.CharField(source="community.slug", read_only=True)
    location = serializers.CharField(source="venue", read_only=True)
    attendees_count = serializers.SerializerMethodField()

    def get_attendees_count(self, obj) -> int:
        # Use annotated value if available (from optimized query), else fallback
        if hasattr(obj, '_annotated_attendees_count'):
            return obj._annotated_attendees_count or 0
        # Fallback: Count approved or attended registrations
        return obj.eventregistration_set.filter(
            status__in=["approved", "attended"]
        ).count()

    def get_is_registered(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return EventRegistration.objects.filter(event=obj, user=request.user).exists()
        return False

    def validate_title(self, value):
        """Sanitize event title."""
        return sanitize_title(value)

    def validate_description(self, value):
        """Sanitize event description (allows limited HTML)."""
        return sanitize_description(value)

    def validate_capacity(self, value):
        """Validate capacity is within bounds."""
        try:
            return validate_capacity(value)
        except SanitizationError as e:
            raise serializers.ValidationError(str(e))

    def validate_price(self, value):
        """Validate price is a valid decimal."""
        try:
            return validate_price(value)
        except SanitizationError as e:
            raise serializers.ValidationError(str(e))

    def validate(self, attrs):
        """
        Cross-field validation:
        - end_time must be after start_time
        - capacity must be >= 0 (if provided)
        - community cannot be changed once event is created
        """
        # --- time validation ---
        start = attrs.get("start_time")
        end = attrs.get("end_time")

        # When updating, fall back to existing values if one is missing
        if self.instance is not None:
            if start is None:
                start = self.instance.start_time
            if end is None:
                end = self.instance.end_time

        if start and end and end <= start:
            raise serializers.ValidationError(
                {"end_time": "end_time must be after start_time."}
            )

        # --- capacity validation ---
        capacity = attrs.get("capacity")
        if self.instance is not None and capacity is None:
            capacity = self.instance.capacity

        if capacity is not None and capacity < 0:
            raise serializers.ValidationError(
                {"capacity": "capacity cannot be negative."}
            )

        # --- community consistency: prevent changing community on update ---
        incoming_community_id = attrs.get("community_id", None)
        if self.instance is not None:
            # Event already exists: community is set and should not be changed
            if incoming_community_id is not None:
                if (
                    self.instance.community_id is not None
                    and incoming_community_id != self.instance.community_id
                ):
                    raise serializers.ValidationError(
                        {"community_id": "Cannot change community of an existing event."}
                    )

        return attrs

    def create(self, validated_data):
        # Remove community_id so it doesn't go into Event.objects.create(...)
        validated_data.pop("community_id", None)
        return super().create(validated_data)


# -----------------------------------------
# REGISTRATION SERIALIZER
# -----------------------------------------
class RegistrationSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    qr_code = serializers.CharField(source="attendance.qr_code", read_only=True)
    checked_in_at = serializers.DateTimeField(source="attendance.check_in", read_only=True)
    has_certificate = serializers.SerializerMethodField()

    class Meta:
        model = EventRegistration
        fields = [
            "id",
            "user",
            "event",
            "registered_at",
            "status",
            "approved",
            "username",
            "qr_code",
            "checked_in_at",
            "has_certificate",
            "guests_count",
        ]
        read_only_fields = ["user", "registered_at", "approved", "qr_code", "checked_in_at", "status"]

    def get_has_certificate(self, obj):
        return hasattr(obj, "certificate")


# -----------------------------------------
# ATTENDANCE SERIALIZER
# -----------------------------------------
class AttendanceSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source="registration.user.username", read_only=True)
    event = serializers.CharField(source="registration.event.title", read_only=True)

    class Meta:
        model = EventAttendance
        fields = ["id", "user", "event", "check_in", "check_out", "qr_code"]


# -----------------------------------------
# CERTIFICATE SERIALIZER
# -----------------------------------------
class CertificateSerializer(serializers.ModelSerializer):
    event = serializers.CharField(
        source="registration.event.title",
        read_only=True
    )

    event_id = serializers.IntegerField(
        source="registration.event.id",
        read_only=True
    )

    user = serializers.CharField(
        source="registration.user.username",
        read_only=True
    )

    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = [
            "id",
            "event",
            "event_id",
            "user",
            "issued_at",
            "cert_token",
            "pdf_url",
        ]
        read_only_fields = fields

    def get_pdf_url(self, obj):
        request = self.context.get("request")
        if obj.pdf and request:
            return request.build_absolute_uri(obj.pdf.url)
        if obj.pdf:
            return obj.pdf.url
        return None


# -----------------------------------------
# ANNOUNCEMENTS
# -----------------------------------------
class AnnouncementSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source="event.title", read_only=True)
    posted_by_username = serializers.CharField(source="posted_by.username", read_only=True)

    class Meta:
        model = Announcement
        fields = [
            "id",
            "event",
            "event_title",
            "posted_by",
            "posted_by_username",
            "title",
            "body",
            "is_important",
            "media_image",
            "created_at",
        ]
        read_only_fields = ["event", "posted_by", "created_at"]


# -----------------------------------------
# FEEDBACK
# -----------------------------------------
class EventFeedbackSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source="event.title", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = EventFeedback
        fields = [
            "id",
            "event",
            "event_title",
            "user",
            "username",
            "rating",
            "comment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["event", "user", "created_at", "updated_at"]

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def validate(self, attrs):
        """
        Extra safety: prevent creating *duplicate* feedback for the same
        (event, user) pair when those are passed via serializer.

        In your current SubmitFeedbackView flow, event/user are attached
        in save(), so this mostly protects any other serializer-based usage.
        """
        request = self.context.get("request")

        # Try to infer user
        user = attrs.get("user") or getattr(self.instance, "user", None)
        if request is not None and user is None:
            user = getattr(request, "user", None)

        # Try to infer event
        event = attrs.get("event") or getattr(self.instance, "event", None)

        if user is not None and event is not None:
            qs = EventFeedback.objects.filter(user=user, event=event)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise serializers.ValidationError(
                    "Feedback for this event from this user already exists."
                )

        return attrs

# -----------------------------------------
# COMMUNITY MEMBERSHIP
# -----------------------------------------
class CommunityMembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    community_name = serializers.CharField(source="community.name", read_only=True)
    community_slug = serializers.CharField(source="community.slug", read_only=True)
    stats = serializers.SerializerMethodField()

    class Meta:
        model = CommunityMembership
        fields = [
            "id",
            "community",
            "community_name",
            "community_slug",
            "user",
            "username",
            "role",
            "is_active",
            "is_default",
            "last_active_at",
            "joined_at",
            "stats",
        ]
        read_only_fields = ["community", "user", "joined_at", "is_default", "last_active_at"]

    def get_stats(self, obj):
        try:
            stats = UserCommunityStats.objects.get(user=obj.user, community=obj.community)
            return {
                "total_xp": stats.total_xp,
                "current_level": stats.current_level,
                "events_attended": stats.events_attended,
                "events_hosted": stats.events_hosted
            }
        except UserCommunityStats.DoesNotExist:
            return {
                "total_xp": 0,
                "current_level": 1,
                "events_attended": 0,
                "events_hosted": 0
            }


# -----------------------------------------
# EVENT TEAM
# -----------------------------------------
class EventTeamMemberSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = EventTeamMember
        fields = [
            "id",
            "event",
            "user_id",
            "username",
            "role",
            "is_active",
            "added_at",
        ]
        read_only_fields = [
            "id",
            "event",
            "user_id",
            "username",
            "is_active",
            "added_at",
        ]



# -----------------------------------------
# VOLUNTEERS
# -----------------------------------------
class EventVolunteerSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    user_avatar = serializers.CharField(source="user.profile_picture", read_only=True)
    verified_by_username = serializers.CharField(source="verified_by.username", read_only=True)

    class Meta:
        from .models import EventVolunteer
        model = EventVolunteer
        fields = [
            "id",
            "event",
            "user",
            "username",
            "user_avatar",
            "role",
            "status",
            "verified_by",
            "verified_by_username",
            "note",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "event",
            "user",
            "status",
            "verified_by",
            "note",
            "created_at",
        ]
