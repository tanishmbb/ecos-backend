#  cos-backend/core/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import secrets

class DomainActivity(models.Model):
    """
    Immutable ledger of all business-significant actions in the system.
    Source of truth for: Feeds, Notifications, Analytics, Reputation.
    """
    VISIBILITY_PUBLIC = "public"
    VISIBILITY_COMMUNITY = "community"
    VISIBILITY_PRIVATE = "private"

    VISIBILITY_CHOICES = [
        (VISIBILITY_PUBLIC, "Public"),
        (VISIBILITY_COMMUNITY, "Community-Only"),
        (VISIBILITY_PRIVATE, "Private"),
    ]

    # Who did it?
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activities",
    )

    # What happened? (e.g., 'event.published')
    verb = models.CharField(max_length=64, db_index=True)

    # To what? (Generic Foreign Key)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    # context (Where?)
    community = models.ForeignKey(
        "Community",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="activities",
    )

    # Scoping
    visibility = models.CharField(
        max_length=16,
        choices=VISIBILITY_CHOICES,
        default=VISIBILITY_COMMUNITY,
        db_index=True,
    )

    # Extra data (Snapshot logic, e.g., "Event Title" at time of logging)
    metadata = models.JSONField(default=dict, blank=True)

    STATUS_ACTIVE = "active"
    STATUS_REVOKED = "revoked"
    STATUS_DELETED = "deleted"
    STATUS_SUPERSEDED = "superseded"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_REVOKED, "Revoked"),
        (STATUS_DELETED, "Deleted"),
        (STATUS_SUPERSEDED, "Superseded"),
    ]

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    # Redaction / Supersession Strategy
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )

    class Meta:
        verbose_name_plural = "Domain Activities"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["community", "-timestamp"]),  # Feed query optimization
            models.Index(fields=["actor", "-timestamp"]),      # Profile feed
        ]

    def __str__(self):
        return f"{self.actor} - {self.verb} - {self.timestamp}"

class Announcement(models.Model):
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="core_announcements",
    )
    # Use string reference to avoid importing Event here
    # Use string reference to avoid importing Event here
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="core_announcements",
        help_text="DEPRECATED: Use GenericFK below for new modules."
    )

    # 🔹 Generic Link (for n-COS, s-COS, etc.)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")
    title = models.CharField(max_length=255)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"], name="core_announcement_created_idx"),
        ]

    def __str__(self):
        return self.title


class FeedItem(models.Model):
    FEED_TYPE_CHOICES = (
        ("event", "Event"),
        ("announcement", "Announcement"),
        ("certificate", "Certificate"),
        ("system", "System Message"),
    )

    type = models.CharField(max_length=20, choices=FEED_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    # Linked models — use string references to avoid imports & circular issues
    # Linked models — use string references to avoid imports & circular issues
    # DEPRECATED: These fields are event-locked. Use 'activity' or 'content_object' source.
    event = models.ForeignKey(
        "events.Event",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="feed_items",
    )
    announcement = models.ForeignKey(
        "core.Announcement",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="feed_items",
    )
    certificate = models.ForeignKey(
        "events.Certificate",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="feed_items",
    )

    # 🔹 The New Source of Truth
    activity = models.ForeignKey(
        DomainActivity,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="feed_items"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"], name="feeditem_created_idx"),
            models.Index(fields=["type"], name="feeditem_type_idx"),
        ]

    def __str__(self):
        return f"{self.type} - {self.created_at}"


class FeedLike(models.Model):
    feed_item = models.ForeignKey(
        FeedItem,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="liked_feed_items",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("feed_item", "user")
        indexes = [
            models.Index(fields=["feed_item"], name="feed_like_item_idx"),
        ]

    def __str__(self):
        return f"{self.user} likes {self.feed_item}"


class FeedComment(models.Model):
    feed_item = models.ForeignKey(
        FeedItem,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="feed_comments",
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["feed_item", "created_at"], name="feed_comment_item_idx"),
        ]

    def __str__(self):
        return f"{self.user} commented on {self.feed_item}"


class Community(models.Model):
    """
    A community / organization / club inside COS.
    Events and other modules can be scoped to a community.
    """
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    # 🔹 Branding fields
    logo = models.ImageField(
        upload_to="communities/logos/",
        null=True,
        blank=True,
        help_text="Community logo used in UI & certificates",
    )
    primary_color = models.CharField(
        max_length=7,
        blank=True,
        help_text="Primary HEX color (e.g. #FF5733)",
    )
    certificate_template = models.ImageField(
        upload_to="communities/cert_templates/",
        null=True,
        blank=True,
        help_text="Optional certificate background/template image",
    )

    # 🔹 Privacy
    is_private = models.BooleanField(
        default=False,
        help_text="If True, community content is hidden from non-members.",
    )

    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="communities_created",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["slug"], name="community_slug_idx"),
        ]

    def __str__(self):
        return self.name


class CommunityMembership(models.Model):
    """
    Per-community role for a user.
    A user can have different roles in different communities.
    """
    ROLE_OWNER = "owner"
    ROLE_ORGANIZER = "organizer"
    ROLE_MEMBER = "member"
    ROLE_PARTICIPANT = "participant"  # New default
    ROLE_ADMIN = "admin"

    ROLE_CHOICES = [
        (ROLE_OWNER, "Owner"),
        (ROLE_ORGANIZER, "Organizer"),
        (ROLE_MEMBER, "Member"),
        (ROLE_PARTICIPANT, "Participant"),
        (ROLE_ADMIN, "Admin"),
    ]

    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_memberships",
    )
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default=ROLE_PARTICIPANT)
    is_active = models.BooleanField(default=True)

    # 🔹 NEW: active / default context for this user
    is_default = models.BooleanField(
        default=False,
        help_text="If True, this is the user's active/default community.",
    )
    last_active_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this community was set as active for the user.",
    )

    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("community", "user")
        indexes = [
            models.Index(
                fields=["community", "role"],
                name="membership_community_role_idx",
            ),
            models.Index(
                fields=["user", "is_default"],
                name="membership_user_default_idx",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} @ {self.community.name} ({self.role})"
class CommunityInvite(models.Model):
    """
    Invite tokens to join a community.
    A user with a valid token can join with the given role (usually 'member').
    """

    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="invites",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_community_invites",
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Opaque token used to join this community via invite.",
    )

    # Role granted to the joining user (default: member)
    role = models.CharField(
        max_length=32,
        default=CommunityMembership.ROLE_MEMBER,
        help_text="Role the joining user will receive.",
    )

    max_uses = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of times this invite can be used. Null = unlimited.",
    )
    used_count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="If set, invite becomes invalid after this time.",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="If false, invite cannot be used even if not expired.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["token"], name="community_invite_token_idx"),
        ]

    def __str__(self):
        return f"Invite for {self.community.name} ({self.token[:8]}...)"

    @classmethod
    def generate_token(cls) -> str:
        """
        Generate a random, URL-safe token.
        """
        return secrets.token_urlsafe(32)[:64]

    def is_valid_now(self) -> bool:
        """
        Check if this invite is currently usable.
        """
        if not self.is_active:
            return False

        if self.expires_at and timezone.now() > self.expires_at:
            return False

        if self.max_uses is not None and self.used_count >= self.max_uses:
            return False

        return True

    def mark_used(self, save: bool = True):
        """
        Increment used_count and deactivate if max_uses reached.
        """
        self.used_count += 1
        if self.max_uses is not None and self.used_count >= self.max_uses:
            self.is_active = False

        if save:
            self.save(update_fields=["used_count", "is_active"])

class MembershipApplication(models.Model):
    """
    Application process for a Participant to become a Member.
    """
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="membership_applications")
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="membership_applications")

    # Why do they want to join?
    intent = models.TextField(help_text="Why the user wants to be a member")
    skills = models.JSONField(default=list, blank=True, help_text="Relevant skills")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_applications"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "community") # One active application per user per community? Logic can handle re-applications later.
        indexes = [
            models.Index(fields=["community", "status"], name="memb_app_status_idx"),
        ]

class CommunityToDo(models.Model):
    """
    Internal tasks for Community Members.
    NOT visible to Participants.
    """
    STATUS_PLANNED = "planned"
    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_ARCHIVED = "archived"

    STATUS_CHOICES = [
        (STATUS_PLANNED, "Planned"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    PRIORITY_LOW = "low"
    PRIORITY_MEDIUM = "medium"
    PRIORITY_HIGH = "high"

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, "Low"),
        (PRIORITY_MEDIUM, "Medium"),
        (PRIORITY_HIGH, "High"),
    ]

    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="todos")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PLANNED)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_todos"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_todos"
    )

    due_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority", "-created_at"]
        indexes = [
            models.Index(fields=["community", "status"], name="todo_comm_status_idx"),
        ]

class UserAccomplishment(models.Model):
    """
    The ledger of action. Proof of work.
    """
    TYPE_EVENT = "event"
    TYPE_PROJECT = "project"
    TYPE_ROLE = "role"
    TYPE_VOLUNTEER = "volunteer"
    TYPE_OTHER = "other"

    TYPE_CHOICES = [
        (TYPE_EVENT, "Event"),
        (TYPE_PROJECT, "Project"),
        (TYPE_ROLE, "Role"),
        (TYPE_VOLUNTEER, "Volunteer"),
        (TYPE_OTHER, "Other"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="accomplishments")
    community = models.ForeignKey(Community, on_delete=models.SET_NULL, null=True, blank=True, related_name="accomplishments")

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    category = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_OTHER)
    date_earned = models.DateField(default=timezone.now)

    # Verification
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_accomplishments"
    )

    # Linkage (Generic or specific?)
    # Let's keep it loose for now, maybe add metadata
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_earned"]
        indexes = [
            models.Index(fields=["user", "category"], name="acc_user_cat_idx"),
        ]
