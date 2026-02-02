# core/constants.py

# --- Activity Verbs (Standard Registry) ---

# Event Lifecycle
ACTIVITY_EVENT_CREATED = "event.created"
ACTIVITY_EVENT_PUBLISHED = "event.published"
ACTIVITY_EVENT_CANCELED = "event.canceled"
ACTIVITY_EVENT_REGISTERED = "event.registered" # User registered for event
ACTIVITY_EVENT_ATTENDED = "event.attended"  # Verified check-in

# Community
ACTIVITY_MEMBER_JOINED = "community.joined"
ACTIVITY_MEMBER_LEFT = "community.left"

# Content
ACTIVITY_ANNOUNCEMENT_POSTED = "announcement.posted"

# Credentials
ACTIVITY_CERTIFICATE_ISSUED = "certificate.issued"
ACTIVITY_CERTIFICATE_REVOKED = "certificate.revoked"

# Reputation (Meta-activity)
ACTIVITY_REPUTATION_CHANGE = "reputation.change"
ACTIVITY_PENALTY = "reputation.penalty" # Negative actions
ACTIVITY_MANUAL_ADJUSTMENT = "reputation.adjustment" # Admin intervention

# Projects (n-COS)
ACTIVITY_PROJECT_CREATED = "project.created"
ACTIVITY_PROJECT_COMPLETED = "project.completed"
ACTIVITY_PROJECT_JOINED = "project.joined"
