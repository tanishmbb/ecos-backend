from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from events.models import Event
from core.models import Community, CommunityMembership
from django.urls import reverse
from rest_framework.test import APIClient
from core.models import Community, CommunityMembership
from events.models import Event


User = get_user_model()


class CommunityAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create two users
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="ownerpass",
        )
        self.other_user = User.objects.create_user(
            username="member",
            email="member@example.com",
            password="memberpass",
        )

        # Auth as owner by default
        self.client.force_authenticate(user=self.owner)

        # Use URL names instead of hard-coded paths
        self.communities_url = reverse("communities-list-create")

    def test_create_community_makes_owner_membership(self):
        payload = {
            "name": "Test Community",
            "slug": "test-community",
            "description": "Test description",
        }

        response = self.client.post(self.communities_url, payload, format="json")
        # If this fails, print status & content
        self.assertEqual(
            response.status_code,
            201,
            f"Status: {response.status_code}, Content: {getattr(response, 'data', response.content)}",
        )

        community = Community.objects.get(slug="test-community")
        self.assertEqual(community.created_by, self.owner)

        membership = CommunityMembership.objects.get(
            community=community,
            user=self.owner,
        )
        self.assertEqual(membership.role, CommunityMembership.ROLE_OWNER)
        self.assertTrue(membership.is_active)

    def test_list_communities_only_shows_my_memberships(self):
        # Create two communities
        c1 = Community.objects.create(
            name="Owner Community",
            slug="owner-community",
            description="Owner's",
            created_by=self.owner,
        )
        c2 = Community.objects.create(
            name="Other Community",
            slug="other-community",
            description="Other's",
            created_by=self.other_user,
        )

        # Add memberships
        CommunityMembership.objects.create(
            community=c1,
            user=self.owner,
            role=CommunityMembership.ROLE_OWNER,
            is_active=True,
        )
        CommunityMembership.objects.create(
            community=c2,
            user=self.other_user,
            role=CommunityMembership.ROLE_OWNER,
            is_active=True,
        )

        response = self.client.get(self.communities_url)
        self.assertEqual(
            response.status_code,
            200,
            f"Status: {response.status_code}, Content: {getattr(response, 'data', response.content)}",
        )

        names = {c["name"] for c in response.data}
        self.assertIn("Owner Community", names)
        self.assertNotIn("Other Community", names)

    def test_owner_can_add_member(self):
        # Create community with owner membership
        community = Community.objects.create(
            name="Team Community",
            slug="team-community",
            description="Team",
            created_by=self.owner,
        )
        CommunityMembership.objects.create(
            community=community,
            user=self.owner,
            role=CommunityMembership.ROLE_OWNER,
            is_active=True,
        )

        url = reverse("communities-add-member", kwargs={"community_id": community.id})
        payload = {
            "user_id": self.other_user.id,
            "role": CommunityMembership.ROLE_ORGANIZER,
        }

        response = self.client.post(url, payload, format="json")
        self.assertIn(
            response.status_code,
            [200, 201],
            f"Status: {response.status_code}, Content: {getattr(response, 'data', response.content)}",
        )

        membership = CommunityMembership.objects.get(
            community=community,
            user=self.other_user,
        )
        self.assertEqual(membership.role, CommunityMembership.ROLE_ORGANIZER)
        self.assertTrue(membership.is_active)

    def test_non_owner_cannot_add_member(self):
        # Create community where other_user is member but not owner
        community = Community.objects.create(
            name="Restricted Community",
            slug="restricted-community",
            description="Restricted",
            created_by=self.owner,
        )
        # Owner membership
        CommunityMembership.objects.create(
            community=community,
            user=self.owner,
            role=CommunityMembership.ROLE_OWNER,
            is_active=True,
        )
        # Make other_user a normal member
        CommunityMembership.objects.create(
            community=community,
            user=self.other_user,
            role=CommunityMembership.ROLE_MEMBER,
            is_active=True,
        )

        # Authenticate as non-owner
        self.client.force_authenticate(user=self.other_user)

        url = reverse("communities-add-member", kwargs={"community_id": community.id})
        payload = {
            "user_id": self.owner.id,
            "role": CommunityMembership.ROLE_ADMIN,
        }

        response = self.client.post(url, payload, format="json")
        self.assertEqual(
            response.status_code,
            403,
            f"Status: {response.status_code}, Content: {getattr(response, 'data', response.content)}",
        )
    def test_owner_can_create_event_in_community(self):
        community = Community.objects.create(
            name="Event Community",
            slug="event-community",
            description="For events",
            created_by=self.owner,
        )
        CommunityMembership.objects.create(
            community=community,
            user=self.owner,
            role=CommunityMembership.ROLE_OWNER,
            is_active=True,
        )

        # 🔥 IMPORTANT: use events-list-create, NOT communities-list-create
        url = reverse("events-list-create")
        payload = {
            "title": "Community Event",
            "description": "An event in a community",
            "start_time": "2030-01-01T10:00:00Z",
            "end_time": "2030-01-01T12:00:00Z",
            "capacity": 100,
            "venue": "Main Hall",
            "community_id": community.id,
        }

        response = self.client.post(url, payload, format="json")
        self.assertEqual(
            response.status_code,
            201,
            f"Status: {response.status_code}, Content: {getattr(response, 'data', response.content)}",
        )

        event = Event.objects.get(title="Community Event")
        self.assertEqual(event.community, community)
        self.assertEqual(event.organizer, self.owner)

    def test_non_member_cannot_create_event_in_community(self):
        community = Community.objects.create(
            name="Restricted Event Community",
            slug="restricted-event-community",
            description="Restricted",
            created_by=self.owner,
        )
        CommunityMembership.objects.create(
            community=community,
            user=self.owner,
            role=CommunityMembership.ROLE_OWNER,
            is_active=True,
        )

        # Auth as user who is NOT a member of this community
        self.client.force_authenticate(user=self.other_user)

        url = reverse("events-list-create")
        payload = {
            "title": "Should Fail",
            "description": "This should not be allowed",
            "start_time": "2030-01-01T10:00:00Z",
            "end_time": "2030-01-01T12:00:00Z",
            "capacity": 50,
            "venue": "Somewhere",
            "community_id": community.id,
        }

        response = self.client.post(url, payload, format="json")
        self.assertEqual(
            response.status_code,
            403,
            f"Status: {response.status_code}, Content: {getattr(response, 'data', response.content)}",
        )
    def test_community_overview_requires_membership(self):
        community = Community.objects.create(
            name="No Access Community",
            slug="no-access-community",
            description="Private",
            created_by=self.owner,
        )

        # No membership for other_user
        self.client.force_authenticate(user=self.other_user)

        url = reverse("community-overview", kwargs={"community_id": community.id})
        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            403,
            f"Status: {response.status_code}, Content: {getattr(response, 'data', response.content)}",
        )

    def test_community_overview_returns_stats_for_owner(self):
        community = Community.objects.create(
            name="Stats Community",
            slug="stats-community",
            description="Stats test",
            created_by=self.owner,
        )
        CommunityMembership.objects.create(
            community=community,
            user=self.owner,
            role=CommunityMembership.ROLE_OWNER,
            is_active=True,
        )

        # Create one event + one registration + one feedback to populate stats
        event = Event.objects.create(
            community=community,
            organizer=self.owner,
            title="Community Event",
            description="Test",
            start_time="2030-01-01T10:00:00Z",
            end_time="2030-01-01T12:00:00Z",
            capacity=100,
            venue="Hall",
            is_public=True,
        )

        from events.models import EventRegistration, EventFeedback

        reg = EventRegistration.objects.create(event=event, user=self.owner)
        EventFeedback.objects.create(
            event=event,
            user=self.owner,
            rating=5,
            comment="Great",
        )

        self.client.force_authenticate(user=self.owner)

        url = reverse("community-overview", kwargs={"community_id": community.id})
        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            200,
            f"Status: {response.status_code}, Content: {getattr(response, 'data', response.content)}",
        )

        data = response.data
        self.assertIn("community", data)
        self.assertIn("stats", data)
        self.assertEqual(data["community"]["id"], community.id)
        self.assertGreaterEqual(data["stats"]["total_events"], 1)
