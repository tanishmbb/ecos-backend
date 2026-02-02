# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('organizer', 'Organizer'),
        ('admin', 'Admin'),
    )

    role = models.CharField(
        max_length=30,
        choices=ROLE_CHOICES,
        default='student'
    )

    phone = models.CharField(max_length=20, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    interests = models.TextField(blank=True, null=True, help_text="Comma-separated interests")
    profile_picture = models.CharField(max_length=1024, blank=True, null=True)

    verified = models.BooleanField(default=False)
    is_onboarded = models.BooleanField(default=False, help_text="Has the user completed the setup flow?")
    points = models.IntegerField(default=0)

    # 🔹 Smart Profile Sync Fields (Competitive Advantage vs devnovate)
    # These fields enable 1-click event registration by pre-filling common requirements
    institution = models.CharField(max_length=255, blank=True, null=True, help_text="University/Organization")
    graduation_year = models.IntegerField(blank=True, null=True)
    degree = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. B.Tech CSE, MBA")

    # Technical Profile
    skills = models.JSONField(default=list, blank=True, help_text="List of technical skills")
    experience_level = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
            ('expert', 'Expert')
        ],
        blank=True,
        null=True
    )

    # Portfolio & Links
    github_url = models.URLField(blank=True, null=True)
    linkedin_url = models.URLField(blank=True, null=True)
    portfolio_url = models.URLField(blank=True, null=True)
    resume_url = models.URLField(blank=True, null=True)

    # Event Registration Defaults (Reduces friction)
    dietary_preferences = models.CharField(max_length=100, blank=True, null=True, help_text="Vegetarian, Vegan, etc.")
    tshirt_size = models.CharField(
        max_length=5,
        choices=[('XS', 'XS'), ('S', 'S'), ('M', 'M'), ('L', 'L'), ('XL', 'XL'), ('XXL', 'XXL')],
        blank=True,
        null=True
    )
    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True, null=True)

    # Privacy Control (Trust-first approach)
    allow_profile_autofill = models.BooleanField(
        default=True,
        help_text="Allow event registrations to pre-fill from profile (can be disabled)"
    )

    # 🔹 Forenna Identity Layer
    intent = models.TextField(blank=True, null=True, help_text="Why are you here? (Personal Mission Statement)")

    AVAILABILITY_LEARNING = "learning"
    AVAILABILITY_CONTRIBUTING = "contributing"
    AVAILABILITY_LEADING = "leading"
    AVAILABILITY_VOLUNTEERING = "volunteering"

    # Simple JSON list of availability modes
    availability = models.JSONField(default=list, blank=True, help_text="List of availability modes (learning, contributing, etc.)")

    # Domains of interest/work (e.g. AI, Webb3, Design)
    domains = models.JSONField(default=list, blank=True, help_text="List of domains user is active in")

    def __str__(self):
        return self.username
