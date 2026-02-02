from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from users.models import User
from notifications.models import Notification
from events.models import Event
from core.models import Community
from datetime import timedelta
from django.utils import timezone


class NotificationApiTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="noti_user",
            password="pass",
            role="student",
        )

        self.other = User.objects.create_user(
            username="other",
            password="pass",
            role="student",
        )

        self.community = Community.objects.create(
            name="Notif Community",
            slug="notif-community",
            description="",
            is_active=True,
        )

        now = timezone.now()
        self.event = Event.objects.create(
            community=self.community,
            organizer=self.user,
            title="Notif Event",
            description="",
            start_time=now,
            end_time=now + timedelta(hours=1),
            capacity=0,
            venue="",
            is_public=True,
            status=Event.STATUS_APPROVED,
        )

        Notification.objects.create(
            user=self.user,
            type=Notification.TYPE_SYSTEM,
            title="System notice",
            body="Welcome",
            event=self.event,
        )
        Notification.objects.create(
            user=self.user,
            type=Notification.TYPE_EVENT_ANNOUNCEMENT,
            title="Event update",
            body="Details",
            event=self.event,
        )
        Notification.objects.create(
            user=self.other,
            type=Notification.TYPE_SYSTEM,
            title="Other user",
            body="Should not be seen",
            event=self.event,
        )

    def auth(self, user):
        self.client.force_authenticate(user=user)

    def test_list_all_notifications_for_me(self):
        self.auth(self.user)
        resp = self.client.get("/api/core/notifications/me/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        titles = {n["title"] for n in data}
        self.assertIn("System notice", titles)
        self.assertIn("Event update", titles)
        self.assertNotIn("Other user", titles)

    def test_mark_notifications_as_read(self):
        self.auth(self.user)

        # Initially unread count
        resp = self.client.get("/api/core/notifications/me/?unread=true")
        self.assertEqual(resp.status_code, 200)
        unread_before = len(resp.json())
        self.assertGreaterEqual(unread_before, 1)

        # Mark all as read
        resp = self.client.post("/api/core/notifications/me/", {"ids": []}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("marked_read", resp.json())

        # Now unread should be zero
        resp = self.client.get("/api/core/notifications/me/?unread=true")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 0)
