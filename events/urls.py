from django.urls import path, include
from .views import (
    EventListCreateView,
    EventDetailView,
    RegisterEventView,
    CancelRegistrationView,
    EventRegistrationsView,
    EventAnnouncementListCreateView,
    ScanQRView,
    RegistrationQRImageView,
    EventAnalyticsView,
    SubmitFeedbackView,
    OrganizerAnalyticsView,
    IssueCertificateView,
    verify_certificate_view,
    MyUpcomingEventsView,
    MyAnnouncementsView,
    MyPastEventsView,
    MyCertificatesView,
    EventFeedbackListView,
    EventFeedbackStatsView,
    CommunityListCreateView,
    CommunityMembersView,
    AddCommunityMemberView,
    CommunityOverviewView,
    CommunityEventsView,
    MyCommunitiesView,
    SetActiveCommunityView,
    EventTeamMemberListCreateView,
    EventTeamMemberDetailView,
    ActiveContextView,
    PublicCommunityEventsView,
    MyDashboardView,
    OrganizerDashboardView,
    DebugPermissionsView,
    EventApprovalView,
    PublicEventDetailView,
    PublicCommunityListView,
    EventRegistrationStatusView,
    EventRegistrationUpdateView,
    OrganizerAnalyticsTrendsView,
    EventRegistrationExportView,
    TicketTokenView,
    VolunteerForEventView,
    EventVolunteerListView,
    EventVolunteerDetailView,
    LiveAttendanceView,
)

# Teams API is in separate file to avoid circular imports

urlpatterns = [
    path(
    "communities/public/",
    PublicCommunityListView.as_view(),
    name="public-community-list",
    ),

    path("", EventListCreateView.as_view(), name="event-list-root"),
    path(
    "public/event/<int:event_id>/",
    PublicEventDetailView.as_view(),
    name="public-event-detail",
    ),

    # Events
    path(
        "<int:event_id>/register/",
        RegisterEventView.as_view(),
        name="event-register",
    ),

    # Registration status (GET ONLY)
    path(
        "<int:event_id>/registration/",
        EventRegistrationStatusView.as_view(),
        name="event-registration-status",
    ),

    path(
        "<int:event_id>/registrations/",
        EventRegistrationsView.as_view(),
        name="event-registrations",
    ),

    # Cancel (OPTIONAL – can keep unused)
    path(
        "<int:event_id>/cancel/",
        CancelRegistrationView.as_view(),
        name="event-cancel",
    ),
    path(
        "<int:event_id>/<str:action>/",
        EventApprovalView.as_view(),
        name="event-approval",
    ),


    # path("events/", EventListCreateView.as_view(), name="event-list-create"), # Redundant
    path("<int:pk>/", EventDetailView.as_view(), name="event-detail"),
    # Announcements
    path("<int:event_id>/announcements/", EventAnnouncementListCreateView.as_view(), name="event-announcements"),
    path("communities/", CommunityListCreateView.as_view(), name="community-list-create"),

    # QR + attendance
    path("ticket/<int:reg_id>/token/", TicketTokenView.as_view(), name="ticket-token"),
    path("scan/<str:qr_code>/", ScanQRView.as_view(), name="scan-qr"),
    path("attendance/scan/<str:qr_code>/", ScanQRView.as_view(), name="attendance-scan"),

    path("registrations/<int:reg_id>/", EventRegistrationUpdateView.as_view(), name="registration-update"),
    path("registrations/<int:reg_id>/qr_image/", RegistrationQRImageView.as_view(), name="registration-qr-image"),

    # Live attendance panel for organizers
    path("<int:event_id>/attendance/live/", LiveAttendanceView.as_view(), name="live-attendance"),

    # Analytics
    path("<int:event_id>/analytics/", EventAnalyticsView.as_view(), name="event-analytics"),
    path("<int:event_id>/feedback/submit/", SubmitFeedbackView.as_view(), name="event-feedback-submit"),
    # path("events/<int:event_id>/feedback/submit/", SubmitFeedbackView.as_view(), name="submit-feedback"), # Duplicate

    path("<int:event_id>/feedback/", EventFeedbackListView.as_view(), name="event-feedback-list"),
    path("<int:event_id>/feedback/stats/", EventFeedbackStatsView.as_view(), name="event-feedback-stats"),
    path("organizer/analytics/", OrganizerAnalyticsView.as_view(), name="organizer-analytics"),
    path("organizer/analytics/trends/", OrganizerAnalyticsTrendsView.as_view(), name="organizer-analytics-trends"),
    path("organizer/export/registrations/<int:event_id>/", EventRegistrationExportView.as_view(), name="organizer-export-registrations"),
    path("me/organizer-dashboard/", OrganizerDashboardView.as_view(), name="organizer-dashboard"),
    path("debug/permissions/", DebugPermissionsView.as_view(), name="debug-permissions"),

    # Certificates
    path("<int:event_id>/certificate/<int:user_id>/", IssueCertificateView.as_view(), name="issue-certificate"),
    path("<int:event_id>/certificate/verify/<str:cert_token>/", verify_certificate_view, name="verify-certificate"),

    # "My" dashboards
    path("me/upcoming/", MyUpcomingEventsView.as_view(), name="my-upcoming-events"),
    path("me/announcements/", MyAnnouncementsView.as_view(), name="my-announcements"),
    path("me/past/", MyPastEventsView.as_view(), name="my-past-events"),
    path("me/certificates/", MyCertificatesView.as_view(), name="my-certificates"),
    path("me/dashboard/", MyDashboardView.as_view(), name="my-dashboard"),

    # Community-scoped
    path("communities/", CommunityListCreateView.as_view(), name="communities-list-create"),
    path("communities/<int:community_id>/members/", CommunityMembersView.as_view(), name="community-members"),
    path("communities/<int:community_id>/members/add/", AddCommunityMemberView.as_view(), name="community-members-add"),
    path(
    "communities/<int:community_id>/members/add/",
    AddCommunityMemberView.as_view(),
    name="communities-add-member",
    ),
    path("communities/<int:community_id>/overview/", CommunityOverviewView.as_view(), name="community-overview"),
    path("communities/<int:community_id>/events/", CommunityEventsView.as_view(), name="community-events"),
    path("public/<community_slug>/", PublicCommunityEventsView.as_view(), name="public-community-events"),


    path("me/communities/", MyCommunitiesView.as_view(), name="my-communities"),
    path("me/communities/<int:community_id>/set_active/", SetActiveCommunityView.as_view(), name="set-active-community"),

    # 🔹 Event team
    path("<int:event_id>/team/", EventTeamMemberListCreateView.as_view(), name="event-team-list-create"),
    path("<int:event_id>/team/<int:member_id>/", EventTeamMemberDetailView.as_view(), name="event-team-detail"),

    # 🔹 Volunteers
    path("<int:event_id>/volunteer/", VolunteerForEventView.as_view(), name="event-volunteer-apply"),
    path("<int:event_id>/volunteers/", EventVolunteerListView.as_view(), name="event-volunteers-list"),
    path("<int:event_id>/volunteers/<int:pk>/", EventVolunteerDetailView.as_view(), name="event-volunteer-detail"),


    path("me/active-context/", ActiveContextView.as_view(), name="active-context"),

    # Team Formation API (temporarily disabled due to import issues - will fix separately)
    # path("teams/", include('events.urls_teams')),
]
