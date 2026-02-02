# cos-backend/events/activity_verbs.py
"""
e-COS Activity Verbs for DomainActivity.

All activity logging in e-COS should use these constants
to ensure consistency and enable proper filtering/analytics.
"""

# Event Lifecycle
EVENT_CREATED = "event.created"
EVENT_UPDATED = "event.updated"
EVENT_DELETED = "event.deleted"
EVENT_SUBMITTED_FOR_APPROVAL = "event.submitted_for_approval"
EVENT_APPROVED = "event.approved"
EVENT_REJECTED = "event.rejected"
EVENT_PUBLISHED = "event.published"
EVENT_CANCELED = "event.canceled"

# Registration
REGISTRATION_CREATED = "registration.created"
REGISTRATION_APPROVED = "registration.approved"
REGISTRATION_REJECTED = "registration.rejected"
REGISTRATION_CANCELED = "registration.canceled"
REGISTRATION_WAITLISTED = "registration.waitlisted"

# Attendance
ATTENDANCE_CHECK_IN = "attendance.check_in"
ATTENDANCE_CHECK_OUT = "attendance.check_out"

# Certificates
CERTIFICATE_ISSUED = "certificate.issued"
CERTIFICATE_REVOKED = "certificate.revoked"
CERTIFICATE_DOWNLOADED = "certificate.downloaded"
CERTIFICATE_VERIFIED = "certificate.verified"

# Feedback
FEEDBACK_SUBMITTED = "feedback.submitted"
FEEDBACK_UPDATED = "feedback.updated"

# Announcements
ANNOUNCEMENT_CREATED = "announcement.created"
ANNOUNCEMENT_DELETED = "announcement.deleted"

# Team Management
TEAM_MEMBER_ADDED = "team.member_added"
TEAM_MEMBER_REMOVED = "team.member_removed"
TEAM_MEMBER_ROLE_CHANGED = "team.member_role_changed"

# Grouped by category for filtering
VERB_CATEGORIES = {
    "event": [
        EVENT_CREATED, EVENT_UPDATED, EVENT_DELETED,
        EVENT_SUBMITTED_FOR_APPROVAL, EVENT_APPROVED, EVENT_REJECTED,
        EVENT_PUBLISHED, EVENT_CANCELED,
    ],
    "registration": [
        REGISTRATION_CREATED, REGISTRATION_APPROVED, REGISTRATION_REJECTED,
        REGISTRATION_CANCELED, REGISTRATION_WAITLISTED,
    ],
    "attendance": [
        ATTENDANCE_CHECK_IN, ATTENDANCE_CHECK_OUT,
    ],
    "certificate": [
        CERTIFICATE_ISSUED, CERTIFICATE_REVOKED,
        CERTIFICATE_DOWNLOADED, CERTIFICATE_VERIFIED,
    ],
    "feedback": [
        FEEDBACK_SUBMITTED, FEEDBACK_UPDATED,
    ],
    "announcement": [
        ANNOUNCEMENT_CREATED, ANNOUNCEMENT_DELETED,
    ],
    "team": [
        TEAM_MEMBER_ADDED, TEAM_MEMBER_REMOVED, TEAM_MEMBER_ROLE_CHANGED,
    ],
}


def get_all_verbs() -> list:
    """Get all e-COS activity verbs."""
    return [verb for verbs in VERB_CATEGORIES.values() for verb in verbs]


def is_valid_verb(verb: str) -> bool:
    """Check if a verb is a valid e-COS activity verb."""
    return verb in get_all_verbs()
