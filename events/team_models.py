# events/models.py - Add to existing file

class EventTeam(models.Model):
    """
    Team Formation System (Competitive Feature vs devnovate)

    Allows participants to:
    1. Create teams for events
    2. Generate shareable invite links
    3. Auto-register teammates when they join via link

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
        # Frontend will construct full URL
        return f"/teams/join/{self.invite_token}"


class EventTeamMember(models.Model):
    """
    Team membership tracking

    Separate from EventTeamMember (event staff) - this is for participant teams
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
            models.Index(fields=['team', 'joined_at'], name='teammember_team_joined_idx'),
        ]

    def __str__(self):
        return f"{self.user.username} in {self.team.name}"
