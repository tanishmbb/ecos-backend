# events/tests/test_e2e_cos_flow.py

from datetime import timedelta
import uuid

from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count

from rest_framework.test import APITestCase

from core.models import Community, CommunityMembership
from events.models import (
    Event,
    EventRegistration,
    EventAttendance,
    Certificate,
    EventFeedback,
)
from events.views import user_can_edit_event  # permission helper
from events.certificate_generator import generate_certificate_pdf


User = get_user_model()


class COSE2EFlowTests(APITestCase):
    """
    High-level end-to-end tests for the COS backend:

    - Community creation & membership (API)
    - Active community (API)
    - Event (community scoped, ORM)
    - Registration & attendance (ORM + QR API)
    - Certificate issuing (model + generator) + me/certificates (API)
    - Feedback (ORM) + stats (ORM aggregate)
    - "Me" endpoints (API)
    - Public community landing (API)
    """

    def setUp(self):
        # Create users
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="pass1234",
            role="admin",  # elevated role
        )
        self.organizer = User.objects.create_user(
            username="organizer",
            email="org@example.com",
            password="pass1234",
            role="organizer",
        )
        self.attendee = User.objects.create_user(
            username="attendee",
            email="attendee@example.com",
            password="pass1234",
            role="member",
        )

        # Use owner as default authed user in most steps
        self.client.force_login(self.owner)

        now = timezone.now()
        self.start_time = now + timedelta(days=1)
        self.end_time = now + timedelta(days=1, hours=2)

    # ---------- Helper methods ----------

    def _create_community(self):
        """
        Owner creates a community via API.
        """
        payload = {
            "name": "Test Community",
            "slug": "test-community",
            "description": "Community for tests",
            "is_active": True,
        }
        resp = self.client.post("/api/events/communities/", payload, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()
        community_id = data["id"]

        # Ensure membership created
        membership = CommunityMembership.objects.get(
            community_id=community_id,
            user=self.owner,
        )
        self.assertEqual(membership.role, CommunityMembership.ROLE_OWNER)
        return community_id

    def _set_active_community(self, community_id):
        resp = self.client.post(
            f"/api/events/me/communities/{community_id}/set_active/",
            {},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)

    def _create_event_model(self, community_id, organizer=None, title="Test Event"):
        """
        Create an Event directly via ORM.
        """
        if organizer is None:
            organizer = self.owner

        event = Event.objects.create(
            organizer=organizer,
            community_id=community_id,
            title=title,
            description="End-to-end flow test event",
            start_time=self.start_time,
            end_time=self.end_time,
            capacity=100,
            venue="Main Hall",
            is_public=True,
        )
        return event.id

    # ---------- Main E2E test ----------

    def test_full_flow_community_event_qr_certificate_feedback(self):
        """
        Full happy-path:
        - owner creates community (API)
        - owner sets active community (API)
        - owner creates event (ORM)
        - organizer & attendee join community (ORM)
        - attendee registers for event (ORM)
        - organizer scans QR (API: /api/events/scan/<qr_code>/)
        - certificate issued via model + generator
        - attendee feedback stored (ORM)
        - stats computed via ORM aggregate (same as view logic)
        - attendee checks 'me' endpoints (API)
        - public community landing works (API)
        """

        # 1) Create community & set active
        community_id = self._create_community()
        self._set_active_community(community_id)

        # 2) Add organizer & attendee as members in that community
        CommunityMembership.objects.create(
            community_id=community_id,
            user=self.organizer,
            role=CommunityMembership.ROLE_ORGANIZER,
            is_active=True,
        )
        CommunityMembership.objects.create(
            community_id=community_id,
            user=self.attendee,
            role=CommunityMembership.ROLE_MEMBER,
            is_active=True,
        )

        # 3) Owner creates an event in this community (ORM)
        event_id = self._create_event_model(community_id)
        event = Event.objects.get(id=event_id)
        self.assertEqual(event.community_id, community_id)

        # 4) Attendee "registers" for the event (ORM instead of /register/ URL)
        reg = EventRegistration.objects.create(event=event, user=self.attendee)
        reg_id = reg.id

        # Attendance record should exist or be created
        attendance, _ = EventAttendance.objects.get_or_create(registration=reg)
        self.assertIsNone(attendance.check_in)
        self.assertIsNotNone(attendance.qr_code)

        # 5) Organizer scans QR to check-in and check-out (API)
        qr_code = str(attendance.qr_code)
        self.client.force_login(self.organizer)

        # First scan -> check-in
        resp = self.client.post(
            f"/api/events/scan/{qr_code}/",
            {},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        attendance.refresh_from_db()
        self.assertIsNotNone(attendance.check_in)
        self.assertIsNone(attendance.check_out)

        # Second scan -> check-out
        resp = self.client.post(
            f"/api/events/scan/{qr_code}/",
            {},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        attendance.refresh_from_db()
        self.assertIsNotNone(attendance.check_out)

        # 6) Issue certificate via model + generator (same logic as IssueCertificateView)
        cert, created = Certificate.objects.get_or_create(registration=reg)

        if not cert.cert_token:
            cert.cert_token = uuid.uuid4().hex

        if not cert.pdf:
            pdf_path = generate_certificate_pdf(self.attendee, event, cert.id)
            cert.pdf = pdf_path
            cert.save()
        else:
            cert.save()

        self.assertIsNotNone(cert.cert_token)
        self.assertTrue(bool(cert.pdf))

        # 7) Attendee feedback (ORM, no URL dependency)
        # Make event appear as already started for feedback logic
        event.start_time = timezone.now() - timedelta(hours=1)
        event.end_time = timezone.now() + timedelta(hours=1)
        event.save(update_fields=["start_time", "end_time"])

        feedback = EventFeedback.objects.create(
            event=event,
            user=self.attendee,
            rating=5,
            comment="Amazing event!",
        )

        self.assertIsNotNone(feedback.id)

        # 8) Stats via ORM aggregate (similar to EventFeedbackStatsView)
        qs = EventFeedback.objects.filter(event=event)
        agg = qs.aggregate(
            avg_rating=Avg("rating"),
            total=Count("id"),
        )

        self.assertEqual(agg["total"], 1)
        self.assertAlmostEqual(agg["avg_rating"], 5.0, places=1)

        # 9) Attendee checks "me" endpoints (API)
        self.client.force_login(self.attendee)

        # Set active community for attendee as well
        self._set_active_community(community_id)

        resp = self.client.get("/api/events/me/certificates/", format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        cert_list = resp.json()
        self.assertGreaterEqual(len(cert_list), 1)

        resp = self.client.get("/api/events/me/upcoming/", format="json")
        self.assertEqual(resp.status_code, 200, resp.content)

        resp = self.client.get("/api/events/me/past/", format="json")
        self.assertEqual(resp.status_code, 200, resp.content)

        resp = self.client.get("/api/events/me/announcements/", format="json")
        self.assertEqual(resp.status_code, 200, resp.content)

        resp = self.client.get("/api/events/me/active-context/", format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        ctx = resp.json()
        # At least check structure
        self.assertIn("active_community", ctx)
        self.assertIn("membership", ctx)
        self.assertIn("stats", ctx)

        # 10) Public community landing should work (API)
        resp = self.client.get("/api/events/public/test-community/", format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        public_data = resp.json()
        self.assertEqual(public_data["community"]["slug"], "test-community")
        self.assertIn("events", public_data)

    # ---------- Permission check (logic-level) ----------

    def test_member_cannot_edit_event(self):
        """
        Ensure a plain member cannot manage/edit an event in a community.
        We test the core permission helper directly: user_can_edit_event.
        """

        # Owner creates community and event
        community_id = self._create_community()
        CommunityMembership.objects.create(
            community_id=community_id,
            user=self.attendee,
            role=CommunityMembership.ROLE_MEMBER,
            is_active=True,
        )

        event_id = self._create_event_model(community_id)
        event = Event.objects.get(id=event_id)

        # Member should NOT be able to edit/manage the event
        can_edit = user_can_edit_event(self.attendee, event)
        self.assertFalse(can_edit, "Member should not be allowed to edit/manage event")
