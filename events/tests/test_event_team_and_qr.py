from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from datetime import timedelta

from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from core.models import Community, CommunityMembership
from events.models import (
    Event,
    EventRegistration,
    EventAttendance,
    EventTeamMember,
)


User = get_user_model()


class EventTeamAndQRTests(APITestCase):
    def setUp(self):
        self.client = APIClient()

        # ---- Users ----
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="pass1234",
            role="organizer",  # your custom User has role field
        )
        self.organizer = User.objects.create_user(
            username="organizer",
            email="organizer@example.com",
            password="pass1234",
            role="organizer",
        )
        self.member = User.objects.create_user(
            username="member",
            email="member@example.com",
            password="pass1234",
            role="member",
        )
        self.outsider = User.objects.create_user(
            username="outsider",
            email="outsider@example.com",
            password="pass1234",
            role="member",
        )

        # ---- Community ----
        self.community = Community.objects.create(
            name="Test Community",
            slug="test-community",
            description="Test community for event team tests",
            created_by=self.owner,
        )

        # memberships
        self.owner_membership = CommunityMembership.objects.create(
            community=self.community,
            user=self.owner,
            role=CommunityMembership.ROLE_OWNER,
            is_active=True,
        )
        self.organizer_membership = CommunityMembership.objects.create(
            community=self.community,
            user=self.organizer,
            role=CommunityMembership.ROLE_ORGANIZER,
            is_active=True,
        )
        self.member_membership = CommunityMembership.objects.create(
            community=self.community,
            user=self.member,
            role=CommunityMembership.ROLE_MEMBER,
            is_active=True,
        )
        # outsider has no membership

        # ---- Event ----
        now = timezone.now()
        self.event = Event.objects.create(
            title="Team Test Event",
            description="Event for testing team + QR",
            organizer=self.owner,
            community=self.community,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            capacity=100,
        )

        # ---- Registration + attendance for member ----
        self.registration = EventRegistration.objects.create(
            event=self.event,
            user=self.member,
        )
        self.attendance = EventAttendance.objects.create(
            registration=self.registration
        )

        # Base paths (from config: path("api/events/", include("events.urls")))
        self.base_api = "/api/events/"

    # -------------------------
    # Event team management
    # -------------------------
    def test_owner_can_add_event_team_member(self):
        """
        Community owner should be able to add a volunteer as event team.
        """
        self.client.force_authenticate(user=self.owner)

        url = f"{self.base_api}events/{self.event.id}/team/"
        payload = {
            "user_id": self.member.id,
            "role": EventTeamMember.ROLE_VOLUNTEER,
        }

        resp = self.client.post(url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)

        self.assertTrue(
            EventTeamMember.objects.filter(
                event=self.event,
                user=self.member,
                role=EventTeamMember.ROLE_VOLUNTEER,
                is_active=True,
            ).exists()
        )

    def test_non_manager_cannot_add_event_team_member(self):
        """
        Regular member (no manager role) should not be able to add event team.
        """
        self.client.force_authenticate(user=self.member)

        url = f"{self.base_api}events/{self.event.id}/team/"
        payload = {
            "user_id": self.organizer.id,
            "role": EventTeamMember.ROLE_VOLUNTEER,
        }

        resp = self.client.post(url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN, resp.content)

    # -------------------------
    # QR permissions
    # -------------------------
    def test_volunteer_can_scan_qr(self):
        """
        Event volunteer should be allowed to scan QR for attendance.
        """
        # Make member an event volunteer
        EventTeamMember.objects.create(
            event=self.event,
            user=self.member,
            role=EventTeamMember.ROLE_VOLUNTEER,
            is_active=True,
        )

        self.client.force_authenticate(user=self.member)

        qr_code_value = str(self.attendance.qr_code)
        url = f"{self.base_api}scan/{qr_code_value}/"

        resp = self.client.post(url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertIn("message", resp.data)
        self.assertEqual(resp.data["message"], "Check-in successful")

        # Check attendance updated
        self.attendance.refresh_from_db()
        self.assertIsNotNone(self.attendance.check_in)

    def test_random_user_cannot_scan_qr(self):
        """
        A user who is neither community manager nor event team should not scan.
        """
        self.client.force_authenticate(user=self.outsider)

        qr_code_value = str(self.attendance.qr_code)
        url = f"{self.base_api}scan/{qr_code_value}/"

        resp = self.client.post(url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN, resp.content)

    # -------------------------
    # Analytics permissions
    # -------------------------
    def test_host_can_view_event_analytics(self):
        """
        Host (event team) should be able to see event analytics.
        """
        # Make organizer a host (even though they are already organizer; just to test)
        EventTeamMember.objects.create(
            event=self.event,
            user=self.organizer,
            role=EventTeamMember.ROLE_HOST,
            is_active=True,
        )

        self.client.force_authenticate(user=self.organizer)

        url = f"{self.base_api}events/{self.event.id}/analytics/"

        resp = self.client.get(url, format="json")
        # Even if stats are empty, permission should pass (200 or 404 if event stats not found),
        # but in our case we expect 200.
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertIn("event", resp.data)
        self.assertEqual(resp.data["event"], self.event.title)

    def test_random_user_cannot_view_event_analytics(self):
        """
        Outsider (no community membership or team role) should not see analytics.
        """
        self.client.force_authenticate(user=self.outsider)

        url = f"{self.base_api}events/{self.event.id}/analytics/"

        resp = self.client.get(url, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN, resp.content)
