from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.throttling import ScopedRateThrottle
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from django.conf import settings
import qrcode
from io import BytesIO
import os

from events.models import EventAttendance, EventRegistration, EventTeamMember, ScanLog
from events.tasks import issue_certificate_after_attendance
from .generics import api_error

class ScanQRView(APIView):
    """
    POST /api/v1/events/scan/<qr_code>/
    Query params: ?timestamp=1234567890&signature=abcdef...
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "qr-scan"

    def post(self, request, qr_code):
        ip_address = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR"))
        scanner = request.user
        qr_code_str = str(qr_code)

        # --- Security: Dynamic QR Validation ---
        timestamp = request.query_params.get("timestamp")
        signature = request.query_params.get("signature")

        # If we enforce dynamic QRs, we reject requests without signature
        # allowing static QRs only for old events? No, let's secure everything going forward.
        # But for backward compat with existing printed QRs (if any), we might need a flag.
        # Assuming digital-only for now as per instructions.

        if timestamp and signature:
            # Optional: Log that dynamic QR was used, but don't strictly enforce expiration if we want "static" behavior for now.
            # For the user request "keep a static qr", we just skip the expiration check or make it very long.
            # Actually, let's just ignore the timestamp check to allow replay if that's what "static for a user" implies (convenience over strict security).
            pass

        # Enforce nothing for now to allow static QRs


        try:
            attendance = (
                EventAttendance.objects
                .select_related("registration__event", "registration__user")
                .get(qr_code=qr_code)
            )
        except EventAttendance.DoesNotExist:
            ScanLog.objects.create(
                event=None, registration=None, scanned_by=scanner,
                qr_code=qr_code_str, ip_address=ip_address, action=ScanLog.ACTION_INVALID_QR,
            )
            return api_error("Invalid QR code", status.HTTP_404_NOT_FOUND)

        registration = attendance.registration
        event = registration.event

        # --- Time-based Validation ---
        # Scan allowed only during event window (Start - 1h to End + 4h)
        # Using 4 hours buffer for post-event networking checkouts
        time_buffer_start = event.start_time - timezone.timedelta(hours=1)
        time_buffer_end = event.end_time + timezone.timedelta(hours=4)

        if not (time_buffer_start <= timezone.now() <= time_buffer_end):
             # Allow organizer to override? Maybe.
             ScanLog.objects.create(
                event=event, registration=registration, scanned_by=scanner,
                qr_code=qr_code_str, ip_address=ip_address, action=ScanLog.ACTION_UNAUTHORIZED,
            )
             return api_error("Scanning allowed only during event hours.", status.HTTP_403_FORBIDDEN)

        # ... Permissions Check (Contextual) ...
        # Can scanner manage this event?
        # Check community permissions + event team
        can_scan = False

        # 1. Organizer
        if scanner.id == event.organizer_id:
            can_scan = True

        # 2. Team Member
        elif EventTeamMember.objects.filter(event=event, user=scanner, is_active=True).exists():
            can_scan = True

        # 3. Community Admin/Organizer
        elif event.community:
            # Use helper or logic from models to check community role
            # Since we deprecated is_global... we check membership
            from core.models import CommunityMembership
            has_role = CommunityMembership.objects.filter(
                community=event.community,
                user=scanner,
                is_active=True,
                role__in=[CommunityMembership.ROLE_ADMIN, CommunityMembership.ROLE_OWNER, CommunityMembership.ROLE_ORGANIZER]
            ).exists()
            if has_role:
                can_scan = True

        # 4. Superuser
        elif scanner.is_superuser:
            can_scan = True

        if not can_scan:
            ScanLog.objects.create(
                event=event, registration=registration, scanned_by=scanner,
                qr_code=qr_code_str, ip_address=ip_address, action=ScanLog.ACTION_UNAUTHORIZED,
            )
            return api_error("Not authorized to scan for this event.", status.HTTP_403_FORBIDDEN)

        # --- Helper to build enriched attendee data ---
        def build_attendee_data(reg, att):
            user = reg.user
            from events.models import Certificate
            has_cert = Certificate.objects.filter(registration=reg).exists()

            return {
                "attendee_name": f"{user.first_name} {user.last_name}".strip() or user.username,
                "attendee_email": user.email,
                "attendee_username": user.username,
                "registration_id": reg.id,
                "registration_time": reg.registered_at.isoformat() if reg.registered_at else None,
                "guests_count": reg.guests_count,
                "total_headcount": 1 + reg.guests_count,
                "check_in_time": att.check_in.isoformat() if att.check_in else None,
                "check_out_time": att.check_out.isoformat() if att.check_out else None,
                "certificate_eligible": has_cert or (att.check_in is not None),
                "certificate_issued": has_cert,
                "payment_status": getattr(reg, 'payment_status', 'N/A'),
            }

        # CHECK-IN
        if attendance.check_in is None:
            attendance.check_in = timezone.now()
            attendance.save(update_fields=["check_in"])

            # Cert issuance tasks now handled by Signal -> Activity -> Reputation
            # But the legacy task might still be useful for the PDF generation specifically?
            # Yes, task.py handles PDF gen. Signals handle Activity log.
            # We keep issue_certificate_after_attendance for the heavy PDF work.
            issue_certificate_after_attendance.apply_async(args=[attendance.id], countdown=30)

            ScanLog.objects.create(
                event=event, registration=registration, scanned_by=scanner,
                qr_code=qr_code_str, ip_address=ip_address, action=ScanLog.ACTION_CHECK_IN,
            )

            # Track analytics (non-critical)
            try:
                from core.analytics import track_qr_scan
                track_qr_scan(
                    event_id=event.id,
                    user_id=registration.user_id,
                    scanned_by=scanner.id
                )
            except Exception:
                pass

            return Response({
                "action": "check_in",
                "message": "Check-in successful",
                "scanned_by": getattr(scanner, "username", None),
                "scanner_ip": ip_address,
                **build_attendee_data(registration, attendance),
            }, status=status.HTTP_200_OK)

        # CHECK-OUT LOGIC REMOVED - "Once checked in, always checked in"
        if attendance.check_in is not None:
             ScanLog.objects.create(
                event=event, registration=registration, scanned_by=scanner,
                qr_code=qr_code_str, ip_address=ip_address, action=ScanLog.ACTION_ALREADY_COMPLETED,
            )

             return Response({
                "action": "already_completed",
                "message": "Already checked in",
                "scanned_by": getattr(scanner, "username", None),
                "scanner_ip": ip_address,
                **build_attendee_data(registration, attendance),
            }, status=status.HTTP_200_OK)





class RegistrationQRImageView(APIView):
    """
    DEPRECATED: Returns a STATIC QR code image.
    Use TicketTokenView for dynamic QRs in production.
    """
    authentication_classes = []
    permission_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "qr-image"

    def get(self, request, reg_id):
        try:
            reg = EventRegistration.objects.select_related("event", "user").get(pk=reg_id)
        except EventRegistration.DoesNotExist:
            return Response({"error": "Registration not found"}, status=404)

        attendance, created = EventAttendance.objects.get_or_create(registration=reg)
        qr_payload = str(attendance.qr_code)

        qr_img = qrcode.make(qr_payload)
        buffer = BytesIO()
        qr_img.save(buffer, format="PNG")
        buffer.seek(0)

        response = HttpResponse(buffer.getvalue(), content_type="image/png")
        response["Cache-Control"] = "no-store"
        return response


class TicketTokenView(APIView):
    """
    GET /api/v1/events/ticket/<reg_id>/token/
    Returns a short-lived signed token for dynamic QR generation.
    Payload: "UUID" (Frontend appends timestamp? No, backend must sign).

    Actually, to match ScanQRView expectations:
    ScanQRView expects: URL param ?timestamp=...&signature=...
    So the QR Content should be: "{UUID}"
    And the Scanner App appends the timestamp/signature?
    NO. The Scanner App (Organizer) scans the User's screen.
    The User's screen must display a QR containing:
    "https://api.cos.com/scan/{UUID}?timestamp=...&signature=..."
    OR just the raw data: "{UUID}:{TIMESTAMP}:{SIGNATURE}" and Scanner parses it.
    Let's go with raw data for flexibility.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "qr-token" # fast rate limit allowed

    def get(self, request, reg_id):
        try:
            # Only the user themselves can view their ticket token
            reg = get_object_or_404(EventRegistration, pk=reg_id)
            if reg.user != request.user:
                 return api_error("Unauthorized", status.HTTP_403_FORBIDDEN)

            attendance, _ = EventAttendance.objects.get_or_create(registration=reg)
            qr_uuid = str(attendance.qr_code)

            # Generator
            import hmac
            import hashlib
            from django.conf import settings

            now = timezone.now().timestamp()
            payload = f"{qr_uuid}:{now}".encode('utf-8')
            signature = hmac.new(
                settings.SECRET_KEY.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()

            return Response({
                "qr_uuid": qr_uuid,
                "timestamp": now,
                "signature": signature,
                "full_payload": qr_uuid # Static QR
            })
        except Exception as e:
            import traceback
            with open('d:/cos-backend/debug_err.txt', 'w') as f:
                f.write(traceback.format_exc())
            return Response({"error": str(e)}, status=500)


class LiveAttendanceView(APIView):
    """
    GET /api/events/<event_id>/attendance/live/

    Returns live attendance data for the organizer scan panel:
    - Event info
    - Live counters (registered, checked-in, no-shows)
    - Full attendee list with attendance status
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id):
        from events.models import Event, EventRegistration, EventAttendance, Certificate
        from .generics import user_can_edit_event
        from django.db.models import Sum, Count, Q

        try:
            event = Event.objects.select_related('community', 'organizer').get(pk=event_id)
        except Event.DoesNotExist:
            return Response({"error": "Event not found"}, status=404)

        if not user_can_edit_event(request.user, event):
            return api_error("Not authorized", status.HTTP_403_FORBIDDEN)

        # Get all registrations with attendance
        registrations = (
            EventRegistration.objects
            .filter(event=event)
            .select_related('user', 'attendance')
        )

        # Calculate counters
        total_registered = registrations.count()
        total_guests = registrations.aggregate(sum=Sum('guests_count'))['sum'] or 0
        total_headcount = total_registered + total_guests

        checked_in_count = EventAttendance.objects.filter(
            registration__event=event,
            check_in__isnull=False
        ).count()



        # No-shows = registered but not checked in (only after event started)
        now = timezone.now()
        no_shows = 0
        if event.start_time and now > event.start_time:
            no_shows = total_registered - checked_in_count

        # Build attendee list
        attendees = []
        cert_reg_ids = set(
            Certificate.objects.filter(registration__event=event).values_list('registration_id', flat=True)
        )

        for reg in registrations:
            # Safe access (OneToOne)
            att = getattr(reg, 'attendance', None)

            user = reg.user

            # Determine status
            if att and att.check_in:
                att_status = "checked_in"
            else:
                att_status = "registered"

            attendees.append({
                "id": reg.id,
                "name": f"{user.first_name} {user.last_name}".strip() or user.username,
                "email": user.email,
                "username": user.username,
                "guests_count": reg.guests_count,
                "total_headcount": 1 + reg.guests_count,
                "status": att_status,
                "check_in_time": att.check_in.isoformat() if att and att.check_in else None,
                "check_out_time": None,
                "registered_at": reg.registered_at.isoformat() if reg.registered_at else None,
                "certificate_issued": reg.id in cert_reg_ids,
                "payment_status": getattr(reg, 'payment_status', 'N/A'),
            })

        return Response({
            "event": {
                "id": event.id,
                "title": event.title,
                "community_name": event.community.name if event.community else None,
                "community_id": event.community_id,
                "venue": getattr(event, 'venue', None) or getattr(event, 'location', 'TBD'),
                "capacity": event.capacity,
                "start_time": event.start_time.isoformat() if event.start_time else None,
                "end_time": event.end_time.isoformat() if event.end_time else None,
            },
            "counters": {
                "total_registered": total_registered,
                "total_guests": total_guests,
                "total_headcount": total_headcount,
                "checked_in": checked_in_count,
                "no_shows": max(0, no_shows),
            },
            "attendees": attendees,
        })

