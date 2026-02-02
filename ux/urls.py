from django.urls import path
from ux.views.dashboard import UXDashboardSummaryView
from ux.views.dashboard_events import UXDashboardEventsView
from ux.views.dashboard_communities import UXDashboardCommunitiesView
from ux.views.dashboard_notifications import UXDashboardNotificationsView
from ux.views.event_discovery import (
    UXUpcomingEventsView,
    UXMyCommunityEventsView,
    UXTrendingEventsView,
    UXRecommendedEventsView,
)
from ux.views.organizer import (
    UXOrganizerEventsSummaryView,
    UXOrganizerEventStatsView,
    UXOrganizerCommunityAnalyticsView,
)
urlpatterns = [
    path(
        "me/dashboard/summary/",
        UXDashboardSummaryView.as_view(),
        name="ux-dashboard-summary",
    ),
    path(
        "me/dashboard/events/",
        UXDashboardEventsView.as_view(),
        name="ux-dashboard-events",
    ),
    path(
        "me/dashboard/communities/",
        UXDashboardCommunitiesView.as_view(),
        name="ux-dashboard-communities",
    ),
    path(
        "me/dashboard/notifications/",
        UXDashboardNotificationsView.as_view(),
        name="ux-dashboard-notifications",
    ),
    path("events/upcoming/", UXUpcomingEventsView.as_view()),
    path("events/my-communities/", UXMyCommunityEventsView.as_view()),
    path("events/trending/", UXTrendingEventsView.as_view()),
    path("events/recommended/", UXRecommendedEventsView.as_view()),
    path("organizer/events/summary/", UXOrganizerEventsSummaryView.as_view()),
    path("organizer/events/<int:event_id>/stats/", UXOrganizerEventStatsView.as_view()),
    path("organizer/community/analytics/", UXOrganizerCommunityAnalyticsView.as_view()),
]
