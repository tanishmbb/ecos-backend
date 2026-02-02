from django.urls import path
from .views import (
    CommunityJoinView,
    FeedListView,
    AnnouncementCreateView,
    AnnouncementListView,
    CommunityInviteGenerateView,
    CommunityJoinByTokenView,
    CommunityMemberListView,
    CommunityMemberDetailView,
    CommunityOwnershipTransferView,
    CommunityDetailView,
    FeedInteractionView,
    MembershipApplicationCreateView,
    MembershipApplicationListView,
    MembershipApplicationReviewView,
    CommunityToDoListView,
)
from notifications.views import MyNotificationsView


urlpatterns = [
    path(
    "<int:community_id>/join/",
    CommunityJoinView.as_view(),
    name="community-join",
    ),
    path("feed/", FeedListView.as_view(), name="feed-list"),
    path("announcements/", AnnouncementListView.as_view(), name="announcement-list"),
    path("announcements/create/", AnnouncementCreateView.as_view(), name="announcement-create"),

    path(
        "communities/<int:community_id>/invite/generate/",
        CommunityInviteGenerateView.as_view(),
        name="community-invite-generate",
    ),
    path(
        "communities/join/<str:token>/",
        CommunityJoinByTokenView.as_view(),
        name="community-join-by-token",
    ),
    path(
        "communities/<int:community_id>/members/",
        CommunityMemberListView.as_view(),
        name="community-member-list",
    ),
    path(
        "communities/<int:community_id>/members/<int:membership_id>/",
        CommunityMemberDetailView.as_view(),
        name="community-member-detail",
    ),
    path(
        "communities/<int:community_id>/transfer-ownership/",
        CommunityOwnershipTransferView.as_view(),
        name="community-transfer-ownership",
    ),
    path(
        "communities/<int:community_id>/",
        CommunityDetailView.as_view(),
        name="community-detail",
    ),
    path("notifications/me/", MyNotificationsView.as_view(), name="my-notifications"),
    path("feed/<int:feed_item_id>/<str:action>/", FeedInteractionView.as_view(), name="feed-interaction"),

    # Forenna Governance
    path("communities/<int:community_id>/join-request/", MembershipApplicationCreateView.as_view(), name="membership-apply"),
    path("communities/<int:community_id>/member-requests/", MembershipApplicationListView.as_view(), name="membership-requests-list"),
    path("communities/<int:community_id>/member-requests/<int:pk>/review/", MembershipApplicationReviewView.as_view(), name="membership-requests-review"),

    path("communities/<int:community_id>/todos/", CommunityToDoListView.as_view(), name="community-todos"),

]
