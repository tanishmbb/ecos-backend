# events/tests/test_flow.py
import shutil
import tempfile
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.conf import settings
from rest_framework.test import APIClient
from django.utils import timezone
from django.urls import reverse

from events.models import Event, EventRegistration, EventAttendance, Certificate

User = get_user_model()


class EventFlowTest(TestCase):
    def setUp(self):
        # Temporary MEDIA_ROOT for tests (so ReportLab output goes to temp)
        self._orig_media_root = getattr(settings, "MEDIA_ROOT", None)
        self.temp_media = tempfile.mkdtemp(prefix="test_media_")
        settings.MEDIA_ROOT = self.temp_media

        # API clients
        self.client_att = APIClient()
        self.client_org = APIClient()

        # Create users
        self.organizer = User.objects.create_user(username="org", password="pass123")
        # give role attribute if your user model supports it; if not, ignore
        try:
            self.organizer.role = "organizer"
            self.organizer.save()
        except Exception:
            pass

        self.attendee = User.objects.create_user(username="att", password="pass123")
        try:
            self.attendee.role = "member"
            self.attendee.save()
        except Exception:
            pass

        # Authenticate clients
        self.client_org.force_authenticate(self.organizer)
        self.client_att.force_authenticate(self.attendee)

        # Create an event
        self.event = Event.objects.create(
            organizer=self.organizer,
            title="Test Event",
            description="Desc",
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=2),
            capacity=5,
            venue="Test Hall",
            is_public=True
        )

    def tearDown(self):
        # Restore MEDIA_ROOT and remove temp dir
        if self._orig_media_root is not None:
            settings.MEDIA_ROOT = self._orig_media_root
        else:
            delattr(settings, "MEDIA_ROOT")
        shutil.rmtree(self.temp_media, ignore_errors=True)

    def test_full_event_flow(self):
        # 1) Attendee registers
        register_url = reverse('event-register', args=[self.event.id])

        r = self.client_att.post(register_url)
        self.assertIn(r.status_code, (200, 201), msg=f"Register failed: {r.status_code} {r.data if hasattr(r, 'data') else r.content}")

        # Check registration exists
        reg = EventRegistration.objects.filter(event=self.event, user=self.attendee).first()
        self.assertIsNotNone(reg, "Registration object not created")

        # Check attendance row exists and has a qr_code
        attendance = EventAttendance.objects.filter(registration=reg).first()
        self.assertIsNotNone(attendance, "Attendance object not created")
        self.assertIsNotNone(attendance.qr_code, "QR code not set on attendance")

        # 2) Attendee fetches QR image
        qr_img_url = reverse('registration-qr-image', args=[reg.id])
        qr_resp = self.client_att.get(qr_img_url)
        self.assertEqual(qr_resp.status_code, 200, f"QR image request failed: {qr_resp.status_code}")
        self.assertEqual(qr_resp["Content-Type"], "image/png")

        # 3) Organizer scans QR — first scan sets check_in
        scan_url = reverse('attendance-scan', args=[attendance.qr_code])
        scan_resp1 = self.client_org.post(scan_url)
        self.assertEqual(scan_resp1.status_code, 200, f"Scan #1 failed: {scan_resp1.status_code} {scan_resp1.data}")
        attendance.refresh_from_db()
        self.assertIsNotNone(attendance.check_in, "check_in not set after first scan")

        # 4) Organizer scans QR again — second scan sets check_out
        scan_resp2 = self.client_org.post(scan_url)
        self.assertEqual(scan_resp2.status_code, 200, f"Scan #2 failed: {scan_resp2.status_code} {scan_resp2.data}")
        attendance.refresh_from_db()
        self.assertIsNotNone(attendance.check_out, "check_out not set after second scan")

        # 5) Organizer issues certificate
        issue_url = reverse('issue-certificate', args=[self.event.id, self.attendee.id])
        issue_resp = self.client_org.post(issue_url)
        self.assertIn(issue_resp.status_code, (200, 201), f"Issue certificate failed: {issue_resp.status_code} {getattr(issue_resp, 'data', issue_resp.content)}")
        # Fetch certificate from DB
        cert = Certificate.objects.filter(registration=reg).first()
        self.assertIsNotNone(cert, "Certificate row not created")
        # cert_token should be present
         # cert_token should be present
        self.assertTrue(getattr(cert, "cert_token", None), "cert_token not set on Certificate")

        # PDF file should be linked in FileField
        self.assertTrue(getattr(cert, "pdf", None), "Certificate PDF not set on FileField")
        self.assertTrue(cert.pdf.name.startswith("certificates/"))

        # Try to get URL (works for local and S3)
        pdf_url = None
        try:
            pdf_url = cert.pdf.url
        except Exception:
            pdf_url = None
        self.assertIsNotNone(pdf_url, "Certificate PDF URL could not be resolved")

        # 6) Verify certificate via public endpoint
        verify_url = reverse('verify-certificate', args=[self.event.id, cert.cert_token])
        verify_resp = self.client_att.get(verify_url)  # public endpoint, auth not required but okay
        self.assertEqual(verify_resp.status_code, 200, f"Certificate verify failed: {verify_resp.status_code} {verify_resp.data}")
        verify_data = verify_resp.json()
        self.assertTrue(verify_data.get("valid", False), "Certificate verification returned invalid")

        # 7) Analytics endpoints
        analytics_event_url = reverse('event-analytics', args=[self.event.id])
        analytics_resp = self.client_org.get(analytics_event_url)
        self.assertEqual(analytics_resp.status_code, 200, f"Event analytics failed: {analytics_resp.status_code}")
        analytics_data = analytics_resp.json()
        self.assertIn("total_registrations", analytics_data.get("stats", {}), "Analytics missing total_registrations key")

        analytics_org_url = reverse('organizer-analytics')
        analytics_org_resp = self.client_org.get(analytics_org_url)
        self.assertEqual(analytics_org_resp.status_code, 200, f"Organizer analytics failed: {analytics_org_resp.status_code}")
        org_data = analytics_org_resp.json()
        self.assertIn("stats", org_data)

    # -------------------------
    # Extra safety tests
    # -------------------------

    def test_cannot_register_twice_for_same_event(self):
        """
        Second registration attempt for same user+event should fail with 400.
        """
        register_url = reverse('event-register', args=[self.event.id])

        # First registration should succeed
        r1 = self.client_att.post(register_url)
        self.assertIn(r1.status_code, (200, 201))

        # Second registration should fail
        r2 = self.client_att.post(register_url)
        self.assertEqual(r2.status_code, 400)
        if hasattr(r2, "data"):
            self.assertIn("error", r2.data)
            self.assertIn("Already registered", str(r2.data["error"]))

        # Ensure only one registration exists in DB
        count = EventRegistration.objects.filter(event=self.event, user=self.attendee).count()
        self.assertEqual(count, 1)

    def test_event_capacity_enforced(self):
        """
        When event capacity is reached, further registrations should be blocked.
        """
        # Make a small-capacity event
        small_event = Event.objects.create(
            organizer=self.organizer,
            title="Small Event",
            description="Desc",
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1),
            capacity=2,
            venue="Room 1",
            is_public=True,
        )

        register_url = reverse('event-register', args=[small_event.id])

        # Create two extra attendees
        u1 = User.objects.create_user(username="att1", password="pass123")
        u2 = User.objects.create_user(username="att2", password="pass123")
        u3 = User.objects.create_user(username="att3", password="pass123")

        c1 = APIClient()
        c2 = APIClient()
        c3 = APIClient()

        c1.force_authenticate(u1)
        c2.force_authenticate(u2)
        c3.force_authenticate(u3)

        # First two registrations succeed
        r1 = c1.post(register_url)
        r2 = c2.post(register_url)
        self.assertIn(r1.status_code, (200, 201))
        self.assertIn(r2.status_code, (200, 201))

        # Third should fail due to capacity full
        r3 = c3.post(register_url)
        self.assertEqual(r3.status_code, 400)
        if hasattr(r3, "data"):
            self.assertIn("error", r3.data)
            self.assertIn("full", str(r3.data["error"]).lower())

        # Ensure only 2 registrations exist
        self.assertEqual(EventRegistration.objects.filter(event=small_event).count(), 2)

    def test_non_organizer_cannot_view_registrations_or_analytics(self):
        """
        Attendee (non-organizer) should get 403 when trying to:
        - view registrations list
        - view event analytics
        """
        # First, create at least one registration so endpoints have data
        register_url = reverse('event-register', args=[self.event.id])
        self.client_att.post(register_url)

        # Attendee tries to view registrations list -> 403
        regs_url = reverse('event-registrations', args=[self.event.id])
        regs_resp = self.client_att.get(regs_url)
        self.assertEqual(regs_resp.status_code, 403)

        # Attendee tries to view event analytics -> 403
        analytics_event_url = reverse('event-analytics', args=[self.event.id])
        analytics_resp = self.client_att.get(analytics_event_url)
        self.assertEqual(analytics_resp.status_code, 403)
    def test_user_dashboard_endpoints(self):
        """
        Ensure 'my' endpoints return correct data:
        - upcoming events
        - past events (after we move the event to the past)
        - certificates
        """
        # First, register attendee for the event
        register_url = reverse('event-register', args=[self.event.id])
        r = self.client_att.post(register_url)
        self.assertIn(r.status_code, (200, 201))

        # Initially, event is in the future (start_time ~ now), so treat as upcoming.
        upcoming_url = reverse('my-upcoming-events')
        upcoming_resp = self.client_att.get(upcoming_url)
        self.assertEqual(upcoming_resp.status_code, 200)
        self.assertTrue(
            len(upcoming_resp.data) >= 1,
            f"Expected at least one upcoming event, got {len(upcoming_resp.data)}"
        )

        # Move event into the past
        self.event.start_time = timezone.now() - timezone.timedelta(days=2)
        self.event.end_time = timezone.now() - timezone.timedelta(days=1)
        self.event.save()

        # Upcoming should now be empty or at least not include this event
        upcoming_resp2 = self.client_att.get(upcoming_url)
        self.assertEqual(upcoming_resp2.status_code, 200)
        # It's enough to assert that upcoming count does not grow; in this simple test we expect 0
        self.assertEqual(len(upcoming_resp2.data), 0)

        # Past events should now contain this event
        past_url = reverse('my-past-events')
        past_resp = self.client_att.get(past_url)
        self.assertEqual(past_resp.status_code, 200)
        self.assertTrue(
            len(past_resp.data) >= 1,
            f"Expected at least one past event, got {len(past_resp.data)}"
        )
        # optional: verify that our event title appears somewhere
        titles = [e.get("title") for e in past_resp.data]
        self.assertIn(self.event.title, titles)

        # Issue certificate for the attendee
        issue_url = reverse('issue-certificate', args=[self.event.id, self.attendee.id])
        issue_resp = self.client_org.post(issue_url)
        self.assertIn(issue_resp.status_code, (200, 201))

        # 'My certificates' should contain at least one item
        my_certs_url = reverse('my-certificates')
        my_certs_resp = self.client_att.get(my_certs_url)
        self.assertEqual(my_certs_resp.status_code, 200)
        self.assertTrue(
            len(my_certs_resp.data) >= 1,
            "Expected at least one certificate for attendee"
        )
        # Check that the event title matches
        cert_event_titles = [c.get("event") for c in my_certs_resp.data]
        self.assertIn(self.event.title, cert_event_titles)
    def test_event_announcements_flow(self):
        """
        Announcements:
        - Organizer can create announcement for an event.
        - Registered attendee can GET event announcements and my announcements.
        - Non-registered user cannot view event announcements.
        - Attendee cannot POST announcements.
        """
        # Attendee registers for the event
        register_url = reverse("event-register", args=[self.event.id])
        r = self.client_att.post(register_url)
        self.assertIn(r.status_code, (200, 201))

        # Organizer posts an announcement
        announcements_url = reverse("event-announcements", args=[self.event.id])
        payload = {
            "title": "Schedule Update",
            "body": "Event starts 30 minutes earlier.",
            "is_important": True,
        }
        post_resp = self.client_org.post(announcements_url, data=payload, format="json")
        self.assertIn(post_resp.status_code, (200, 201))
        self.assertIn("title", post_resp.data)
        self.assertEqual(post_resp.data["title"], "Schedule Update")

        # Registered attendee can GET announcements for that event
        get_resp_att = self.client_att.get(announcements_url)
        self.assertEqual(get_resp_att.status_code, 200)
        self.assertGreaterEqual(len(get_resp_att.data), 1)

        # Attendee sees the announcement in /me/announcements
        my_ann_url = reverse("my-announcements")
        my_ann_resp = self.client_att.get(my_ann_url)
        self.assertEqual(my_ann_resp.status_code, 200)
        self.assertGreaterEqual(len(my_ann_resp.data), 1)
        titles = [a.get("title") for a in my_ann_resp.data]
        self.assertIn("Schedule Update", titles)

        # Non-registered user cannot GET event announcements
        other_user = User.objects.create_user(username="other", password="pass123")
        client_other = APIClient()
        client_other.force_authenticate(other_user)

        get_resp_other = client_other.get(announcements_url)
        self.assertEqual(get_resp_other.status_code, 403)

        # Attendee cannot POST announcements
        post_resp_att = self.client_att.post(announcements_url, data=payload, format="json")
        self.assertEqual(post_resp_att.status_code, 403)

    def test_event_feedback_flow(self):
        """
        Feedback:
        - Registered attendee can submit feedback after event start.
        - Feedback is created or updated for same user+event.
        - Organizer can list feedback and view stats.
        - Non-registered user cannot submit or view.
        - Dashboard past events show feedback info.
        """
        # Attendee registers
        register_url = reverse("event-register", args=[self.event.id])
        r = self.client_att.post(register_url)
        self.assertIn(r.status_code, (200, 201))

        # Move event to the past so feedback is allowed
        self.event.start_time = timezone.now() - timezone.timedelta(days=2)
        self.event.end_time = timezone.now() - timezone.timedelta(days=1)
        self.event.save()

        submit_url = reverse("submit-feedback", args=[self.event.id])

        # Attendee submits feedback
        payload = {"rating": 5, "comment": "Amazing event!"}
        fb_resp = self.client_att.post(submit_url, data=payload, format="json")
        self.assertIn(fb_resp.status_code, (200, 201))
        self.assertEqual(fb_resp.data.get("rating"), 5)
        self.assertEqual(fb_resp.data.get("comment"), "Amazing event!")

        # Attendee updates feedback
        payload_update = {"rating": 4, "comment": "Pretty good overall"}
        fb_resp2 = self.client_att.post(submit_url, data=payload_update, format="json")
        self.assertEqual(fb_resp2.status_code, 200)
        self.assertEqual(fb_resp2.data.get("rating"), 4)

        # Non-registered user cannot submit feedback
        other = User.objects.create_user(username="fb_other", password="pass123")
        client_other = APIClient()
        client_other.force_authenticate(other)

        fb_resp_other = client_other.post(submit_url, data={"rating": 5}, format="json")
        self.assertEqual(fb_resp_other.status_code, 403)

        # Organizer can list feedback
        list_url = reverse("event-feedback-list", args=[self.event.id])
        list_resp = self.client_org.get(list_url)
        self.assertEqual(list_resp.status_code, 200)
        self.assertGreaterEqual(len(list_resp.data), 1)
        self.assertEqual(list_resp.data[0].get("rating"), 4)

        # Organizer can view feedback stats
        stats_url = reverse("event-feedback-stats", args=[self.event.id])
        stats_resp = self.client_org.get(stats_url)
        self.assertEqual(stats_resp.status_code, 200)
        stats_data = stats_resp.json()
        self.assertIn("average_rating", stats_data)
        self.assertIn("total_feedback", stats_data)

        # Non-registered user cannot view feedback list or stats
        list_resp_other = client_other.get(list_url)
        stats_resp_other = client_other.get(stats_url)
        self.assertEqual(list_resp_other.status_code, 403)
        self.assertEqual(stats_resp_other.status_code, 403)

        # Dashboard: attendee should see feedback info attached to past events
        past_url = reverse("my-past-events")
        past_resp = self.client_att.get(past_url)
        self.assertEqual(past_resp.status_code, 200)
        self.assertGreaterEqual(len(past_resp.data), 1)

        # Find our event in the response
        matching = [e for e in past_resp.data if e.get("id") == self.event.id]
        self.assertTrue(matching, "Expected past events list to contain the test event")
        event_entry = matching[0]

        # Feedback block should indicate feedback given with correct rating
        fb_block = event_entry.get("feedback", {})
        self.assertTrue(fb_block.get("given", False))
        self.assertEqual(fb_block.get("rating"), 4)

        # Since feedback is already given, can_give_feedback should be False
        self.assertFalse(event_entry.get("can_give_feedback", True))
