# events/views.py

import uuid

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from .models import Certificate, EventRegistration
from .certificate_serializer import CertificateSerializer
from .certificate_generator import generate_certificate_pdf


class IssueCertificateView(APIView):
    """
    POST /events/<event_id>/certificate/<user_id>/

    Synchronous version (no Celery).
    - Finds the EventRegistration for (event_id, user_id)
    - Checks that the requester is organizer or admin
    - Creates or reuses a Certificate
    - Generates the PDF if needed
    - Returns the certificate data (including pdf_url)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, event_id, user_id):
        # 1) Find the registration for this event + user
        try:
            reg = EventRegistration.objects.get(event_id=event_id, user_id=user_id)
        except EventRegistration.DoesNotExist:
            return Response({"error": "Registration not found"}, status=status.HTTP_404_NOT_FOUND)

        event = reg.event

        # 2) Permission check: only organizer or admin can issue
        user_role = getattr(request.user, "role", None)
        if not (request.user == event.organizer or user_role == "admin"):
            return Response({"error": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        # 3) Get or create the Certificate row
        cert, created = Certificate.objects.get_or_create(registration=reg)

        # 4) Ensure certificate token exists
        if not cert.cert_token:
            cert.cert_token = uuid.uuid4().hex

        # 5) Generate PDF if new or missing
        if created or not cert.pdf:
            # This function writes the PDF into MEDIA_ROOT/certificates/
            # and returns a relative path like "certificates/certificate_7.pdf"
            pdf_relative_path = generate_certificate_pdf(reg.user, reg.event, cert.id, cert_token=cert.cert_token)
            cert.pdf = pdf_relative_path

        # 6) Save updates
        cert.save()

        # 7) Push to feed (optional, safe try/except)
        try:
            from core.models import FeedItem
            FeedItem.objects.create(type="certificate", certificate=cert)
        except Exception:
            # ignore feed errors; certificate is still issued
            pass

        # 8) Serialize and return certificate data
        serializer = CertificateSerializer(cert, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
# events/tasks.py

from celery import shared_task
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from .models import EventRegistration, Certificate, Announcement
from .certificate_generator import generate_certificate_pdf
from .emails import (
    send_registration_email,
    send_certificate_email,
    send_announcement_email,
)


@shared_task
def send_registration_email_task(registration_id: int):
    """
    Async wrapper for sending registration confirmation email.
    """
    try:
        reg = EventRegistration.objects.select_related("event", "user").get(id=registration_id)
    except EventRegistration.DoesNotExist:
        return

    # We don't have a Django request in Celery; emails code should handle request=None
    try:
        send_registration_email(reg, request=None)
    except Exception:
        # Avoid crashing worker if email fails
        return


@shared_task
def generate_certificate_pdf_task(certificate_id: int):
    """
    Async generation of certificate PDF if needed.
    Can be used for bulk issuance.
    """
    try:
        cert = Certificate.objects.select_related("registration__user", "registration__event").get(
            id=certificate_id
        )
    except Certificate.DoesNotExist:
        return

    # If already has a PDF, skip
    if cert.pdf:
        return

    reg = cert.registration
    user = reg.user
    event = reg.event

    try:
        pdf_relative_path = generate_certificate_pdf(user, event, certificate_id=cert.id)
        cert.pdf = pdf_relative_path
        cert.save(update_fields=["pdf"])
    except Exception:
        # Don't kill worker if generation fails
        return


@shared_task
def send_certificate_email_task(certificate_id: int):
    """
    Async wrapper for sending certificate email.
    """
    try:
        cert = Certificate.objects.select_related("registration__user", "registration__event").get(
            id=certificate_id
        )
    except Certificate.DoesNotExist:
        return

    try:
        send_certificate_email(cert, request=None)
    except Exception:
        return


@shared_task
def send_announcement_email_task(announcement_id: int):
    """
    Async wrapper for sending event announcement emails.
    """
    try:
        ann = Announcement.objects.select_related("event", "posted_by").get(id=announcement_id)
    except Announcement.DoesNotExist:
        return

    try:
        send_announcement_email(ann, request=None)
    except Exception:
        return
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from .models import EventAttendance, Certificate
from .certificate_generator import generate_certificate_pdf
import uuid


@shared_task(bind=True, max_retries=3)
def issue_certificate_after_attendance(self, attendance_id: int):
    try:
        attendance = EventAttendance.objects.select_related(
            "registration__user",
            "registration__event",
        ).get(id=attendance_id)
    except EventAttendance.DoesNotExist:
        return "attendance_not_found"

    # Must be checked in
    if not attendance.check_in:
        return "not_checked_in"

    reg = attendance.registration

    # Idempotency: certificate already exists
    cert, created = Certificate.objects.get_or_create(registration=reg)

    if not cert.cert_token:
        cert.cert_token = uuid.uuid4().hex

    # Generate PDF only if missing
    if not cert.pdf:
        pdf_path = generate_certificate_pdf(
            reg.user,
            reg.event,
            certificate_id=cert.id,
        )
        cert.pdf = pdf_path

    cert.save()
    return "certificate_issued"
