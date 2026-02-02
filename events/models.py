# cos-backend/events/models.py
from django.db import models
from django.conf import settings
import uuid
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class Event(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    TYPE_WORKSHOP = "workshop"
    TYPE_SEMINAR = "seminar"
    TYPE_FEST = "fest"
    TYPE_OTHER = "other"

    TYPE_CHOICES = [
        (TYPE_WORKSHOP, "Workshop"),
        (TYPE_SEMINAR, "Seminar"),
        (TYPE_FEST, "Fest"),
        (TYPE_OTHER, "Other"),
    ]

    community = models.ForeignKey(
        "core.Community",
        on_delete=models.CASCADE,
        related_name="events",
        null=True,
        blank=True,
    )
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='organized_events'
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    capacity = models.PositiveIntegerField(default=0)
    venue = models.CharField(max_length=255, blank=True, null=True)
    banner = models.CharField(max_length=1024, blank=True, null=True)
    is_public = models.BooleanField(default=True)

    # New Fields for COS Event OS
    event_type = models.CharField(max_length=32, choices=TYPE_CHOICES, default=TYPE_OTHER)
    is_paid = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=10, default="INR")
    waitlist_enabled = models.BooleanField(default=False)
    location_lat = models.FloatField(blank=True, null=True)
    location_lng = models.FloatField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_APPROVED,  # or STATUS_PENDING if you want stricter default
    )


    class Meta:
        indexes = [
            models.Index(
                fields=['organizer', 'start_time'],
                name='event_org_start_idx',
            ),
            models.Index(
                fields=['start_time'],
                name='event_start_idx',
            ),
            models.Index(
                fields=['created_at'],
                name='event_created_idx',
            ),
        ]



class EventRegistration(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_WAITLISTED = "waitlisted"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELED = "canceled"
    STATUS_ATTENDED = "attended"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_WAITLISTED, "Waitlisted"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_CANCELED, "Canceled"),
        (STATUS_ATTENDED, "Attended"),
    ]

    PAYMENT_PENDING = "pending"
    PAYMENT_PAID = "paid"
    PAYMENT_REFUNDED = "refunded"
    PAYMENT_SKIPPED = "skipped"

    PAYMENT_CHOICES = [
        (PAYMENT_PENDING, "Pending"),
        (PAYMENT_PAID, "Paid"),
        (PAYMENT_REFUNDED, "Refunded"),
        (PAYMENT_SKIPPED, "Skipped"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    registered_at = models.DateTimeField(auto_now_add=True)

    # Migrating from simple boolean to full status
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)
    approved = models.BooleanField(default=True) # Deprecated, kept for backward compat during migration

    payment_status = models.CharField(max_length=32, choices=PAYMENT_CHOICES, default=PAYMENT_PENDING)
    payment_id = models.CharField(max_length=255, blank=True, null=True)

    guests_count = models.PositiveIntegerField(default=0, help_text="Number of additional guests attending")


    # 🔹 Smart Profile Sync Snapshot (Competitive Advantage)
    # Store profile data at registration time for:
    # 1. Audit trail (user can't change history by editing profile)
    # 2. Organizer access to participant info
    # 3. Certificate generation with accurate data
    snapshot_institution = models.CharField(max_length=255, blank=True, null=True)
    snapshot_degree = models.CharField(max_length=100, blank=True, null=True)
    snapshot_graduation_year = models.IntegerField(blank=True, null=True)
    snapshot_skills = models.JSONField(default=list, blank=True)
    snapshot_dietary = models.CharField(max_length=100, blank=True, null=True)
    snapshot_tshirt_size = models.CharField(max_length=5, blank=True, null=True)
    snapshot_emergency_contact = models.CharField(max_length=100, blank=True, null=True)
    snapshot_emergency_phone = models.CharField(max_length=20, blank=True, null=True)

    # Custom fields for this specific event (organizer-defined)
    custom_responses = models.JSONField(default=dict, blank=True, help_text="Answers to event-specific questions")

    class Meta:
        unique_together = ('user', 'event')
        indexes = [
            # List registrations for an event ordered by time
            models.Index(
                fields=['event', 'registered_at'],
                name='reg_event_registered_idx',
            ),
            # Find registrations for a user in a specific event
            models.Index(
                fields=['user', 'event'],
                name='reg_user_event_idx',
            ),
        ]


class EventAttendance(models.Model):
    registration = models.OneToOneField(
        EventRegistration,
        on_delete=models.CASCADE,
        related_name='attendance'
    )
    check_in = models.DateTimeField(blank=True, null=True)
    check_out = models.DateTimeField(blank=True, null=True)
    # We look this up directly in ScanQRView, so make it unique + indexed
    qr_code = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )

    def __str__(self):
        return f"{self.registration.user.username} - {self.registration.event.title}"

    class Meta:
        indexes = [
            models.Index(
                fields=['qr_code'],
                name='att_qr_code_idx',
            ),
            models.Index(
                fields=['registration'],
                name='att_registration_idx',
            ),
        ]


class Certificate(models.Model):
    # DEPRECATED: Event-locked. Use GenericFK below.
    registration = models.OneToOneField(EventRegistration, on_delete=models.CASCADE, null=True, blank=True)

    # 🔹 Generic Issuance Source (e.g. Project, Membership, or EventRegistration)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    issued_at = models.DateTimeField(auto_now_add=True)
    pdf = models.FileField(upload_to='certificates/', null=True, blank=True)

    # Unique token is used in verify endpoint; ensure it’s indexed
    cert_token = models.CharField(
        max_length=128,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
    )

    # --- New Credential Fields ---
    credential_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    # Revocation support
    revoked_at = models.DateTimeField(null=True, blank=True)
    revocation_reason = models.TextField(blank=True, null=True)

    # Immutable snapshot of issuer (in case community changes branding later)
    issuer_snapshot = models.JSONField(default=dict, blank=True)

    def __str__(self):
        status = "REVOKED" if self.revoked_at else "VALID"
        return f"Certificate ({status}) - {self.registration.user.username}"

    class Meta:
        indexes = [
            models.Index(
                fields=['registration'],
                name='cert_registration_idx',
            ),
            models.Index(fields=['credential_id'], name='cert_credential_img'),
        ]
class ScanLog(models.Model):
    """
    Audit log for QR scans.
    Stores who scanned, what QR, which event/registration (if known),
    IP address, action type, and timestamp.
    """
    ACTION_CHECK_IN = "check_in"
    ACTION_CHECK_OUT = "check_out"
    ACTION_INVALID_QR = "invalid_qr"
    ACTION_UNAUTHORIZED = "unauthorized"
    ACTION_ALREADY_COMPLETED = "already_completed"

    ACTION_CHOICES = [
        (ACTION_CHECK_IN, "Check-in"),
        (ACTION_CHECK_OUT, "Check-out"),
        (ACTION_INVALID_QR, "Invalid QR"),
        (ACTION_UNAUTHORIZED, "Unauthorized"),
        (ACTION_ALREADY_COMPLETED, "Already completed"),
    ]

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="scan_logs",
        null=True,
        blank=True,
    )
    registration = models.ForeignKey(
        EventRegistration,
        on_delete=models.SET_NULL,
        related_name="scan_logs",
        null=True,
        blank=True,
    )
    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="scan_logs",
        null=True,
        blank=True,
    )
    qr_code = models.CharField(max_length=128)
    ip_address = models.CharField(max_length=64, null=True, blank=True)
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["event", "created_at"],
                name="scanlog_event_created_idx",
            ),
            models.Index(
                fields=["qr_code"],
                name="scanlog_qrcode_idx",
            ),
            models.Index(
                fields=["action", "created_at"],
                name="scanlog_action_created_idx",
            ),
        ]

    def __str__(self):
        return f"{self.scanned_by} - {self.qr_code} - {self.action}"
class Announcement(models.Model):
    """
    Announcements made for a specific event.
    Only organizers/admin can create.
    Visible to registrants of that event (and organizer/admin).
    """
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="announcements",
    )
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="event_announcements",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    is_important = models.BooleanField(default=False)

    # 🔹 Visual Post Support
    media_image = models.ImageField(
        upload_to="events/announcements/",
        null=True,
        blank=True,
        help_text="Optional image for visual updates (Instagram-style).",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["event", "created_at"],
                name="announcement_event_created_idx",
            ),
        ]

    def __str__(self):
        return f"{self.event.title} - {self.title}"
class EventFeedback(models.Model):
    """
    Feedback from attendees for an event.
    Each user can give at most one feedback per event.
    """
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="feedbacks",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="event_feedbacks",
    )
    rating = models.PositiveSmallIntegerField()  # we'll enforce 1-5 in serializer
    comment = models.TextField(blank=True)
    is_anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("event", "user")
        indexes = [
            models.Index(
                fields=["event", "created_at"],
                name="feedback_event_created_idx",
            ),
            models.Index(
                fields=["event", "rating"],
                name="feedback_event_rating_idx",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event.title} - {self.user.username} ({self.rating})"


# 🔹 Team Formation System (Competitive Feature vs devnovate)
class EventTeam(models.Model):
    """
    Allows participants to create teams and invite teammates via shareable links.

    Trust mechanisms:
    - Team size limits enforced
    - Creator accountability (tracked via DomainActivity)
    - Organizer visibility and control
    """
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='teams')
    name = models.CharField(max_length=100)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_teams')

    # Invite system
    invite_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    max_size = models.IntegerField(default=4, help_text="Maximum team members")

    # Status
    is_locked = models.BooleanField(default=False, help_text="Prevent new members from joining")
    created_at = models.DateTimeField(auto_now_add=True)

    # Metadata
    description = models.TextField(blank=True, null=True)
    skills_needed = models.JSONField(default=list, blank=True, help_text="Skills the team is looking for")

    class Meta:
        unique_together = ('event', 'name')
        indexes = [
            models.Index(fields=['event', 'created_at'], name='team_event_created_idx'),
            models.Index(fields=['invite_token'], name='team_invite_idx'),
        ]

    def __str__(self):
        return f"{self.name} ({self.event.title})"

    @property
    def current_size(self):
        return self.members.count()

    @property
    def is_full(self):
        return self.current_size >= self.max_size

    @property
    def invite_url(self):
        return f"/teams/join/{self.invite_token}"


class ParticipantTeamMember(models.Model):
    """
    Participant team membership (different from EventTeamMember which is event staff)
    """
    team = models.ForeignKey(EventTeam, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    registration = models.ForeignKey(
        EventRegistration,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Auto-created if user joins via invite link"
    )

    joined_at = models.DateTimeField(auto_now_add=True)
    role = models.CharField(
        max_length=20,
        choices=[
            ('leader', 'Team Leader'),
            ('member', 'Member')
        ],
        default='member'
    )

    class Meta:
        unique_together = ('team', 'user')
        indexes = [
            models.Index(fields=['team', 'joined_at'], name='ptm_team_joined_idx'),
        ]

    def __str__(self):
        return f"{self.user.username} in {self.team.name}"
class EventTeamMember(models.Model):
    """
    Per-event role assignments (host, co-host, volunteer).
    A user must belong to the same community as the event.
    """

    ROLE_HOST = "host"
    ROLE_CO_HOST = "co_host"
    ROLE_VOLUNTEER = "volunteer"

    ROLE_CHOICES = [
        (ROLE_HOST, "Host"),
        (ROLE_CO_HOST, "Co-host"),
        (ROLE_VOLUNTEER, "Volunteer"),
    ]

    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="team_members",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="event_team_memberships",
    )
    role = models.CharField(max_length=32, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("event", "user")
        indexes = [
            models.Index(fields=["event"], name="event_team_event_idx"),
            models.Index(fields=["user"], name="event_team_user_idx"),
            models.Index(fields=["role"], name="event_team_role_idx"),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.role} @ {self.event}"


class EventVolunteer(models.Model):
    """
    Volunteers who are NOT organizing team members but help out.
    They do NOT get admin access.
    They build reputation.
    """
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_COMPLETED = "completed" # Work done & verified

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_COMPLETED, "Completed"),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="volunteers")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="volunteering_gigs")

    role = models.CharField(max_length=64, help_text="What will they do? e.g. 'Registration Desk'")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    # Verification
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_volunteers"
    )

    # Feedback (internal)
    note = models.TextField(blank=True, help_text="Organizer notes on performance")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("event", "user")
        indexes = [
            models.Index(fields=["event", "status"], name="vol_event_status_idx"),
            models.Index(fields=["user", "status"], name="vol_user_status_idx"),
        ]

    def __str__(self):
        return f"{self.user.username} volunteering for {self.event.title}"
