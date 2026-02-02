from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.throttling import ScopedRateThrottle
from rest_framework import status
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
import uuid
import os

from events.models import EventRegistration, Certificate
from core.models import FeedItem
from notifications.models import Notification
from events.serializers import CertificateSerializer
from events.certificate_generator import generate_certificate_pdf
from events.tasks import send_certificate_email_task
from events.emails import send_certificate_email
from .generics import user_can_edit_event, get_active_community_id_for_user

class IssueCertificateView(APIView):
    """
    POST /api/v1/event/<event_id>/certificate/<user_id>/
    - Only the event organizer or admin can call this.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, event_id, user_id):
        try:
            reg = EventRegistration.objects.get(event_id=event_id, user_id=user_id)
        except EventRegistration.DoesNotExist:
            return Response({"error": "Registration not found"}, status=status.HTTP_404_NOT_FOUND)

        event = reg.event
        if not user_can_edit_event(request.user, event):
            return Response({"error": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        cert, created = Certificate.objects.get_or_create(registration=reg)

        if not getattr(cert, "cert_token", None):
            cert.cert_token = uuid.uuid4().hex

        try:
            if created or not cert.pdf:
                pdf_relative_path = generate_certificate_pdf(reg.user, reg.event, cert.id)
                cert.pdf = pdf_relative_path
                cert.save()
            else:
                cert.save()
        except Exception as e:
            return Response(
                {"error": "Failed to generate certificate PDF", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if FeedItem is not None:
            try:
                FeedItem.objects.create(type="certificate", certificate=cert)
            except Exception:
                pass

        try:
            send_certificate_email_task.delay(cert.id)
        except Exception:
            try:
                send_certificate_email(cert, request=request)
            except Exception:
                pass

        serializer = CertificateSerializer(cert, context={"request": request})
        Notification.objects.create(
            user=reg.user,
            event=event,
            type=Notification.TYPE_CERTIFICATE_ISSUED,
            title=f"Certificate issued for {event.title}",
            body="Your certificate has been generated and is now available in your dashboard.",
        )

        # Track analytics
        try:
            from core.analytics import track_certificate_issued
            track_certificate_issued(
                event_id=event.id,
                user_id=reg.user.id,
                cert_id=cert.id,
                community_id=event.community_id if hasattr(event, 'community_id') else None
            )
        except Exception:
            pass  # Non-critical

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MyCertificatesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        certs = (
            Certificate.objects
            .select_related("registration__event", "registration__user")
            .filter(registration__user=request.user)
        )

        community_id = request.query_params.get("community_id") or request.headers.get("X-Community-ID")
        if not community_id:
            community_id = get_active_community_id_for_user(request.user)

        if community_id:
            certs = certs.filter(registration__event__community_id=community_id)

        certs = certs.order_by("-issued_at")

        serializer = CertificateSerializer(certs, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def verify_certificate_view(request, event_id, cert_token):
    request.throttle_scope = "cert-verify"
    cert = get_object_or_404(
        Certificate,
        cert_token=cert_token,
        registration__event_id=event_id,
    )

    pdf_url = None
    signed_url_expiry = None

    # Try Supabase signed URL first (more secure, expires in 10 minutes)
    try:
        from core.supabase_client import get_signed_url
        user_id = cert.registration.user_id
        supabase_path = f"{user_id}/certificate_{cert.id}.pdf"
        signed_url = get_signed_url(supabase_path, expires_in=600)  # 10 min
        if signed_url:
            pdf_url = signed_url
            signed_url_expiry = 600
    except Exception:
        pass

    # Fallback to local storage URL if Supabase not available
    if not pdf_url:
        try:
            if cert.pdf:
                if hasattr(cert.pdf, "url"):
                    pdf_url = request.build_absolute_uri(cert.pdf.url) if request else cert.pdf.url
                else:
                    media_url = getattr(settings, "MEDIA_URL", "/media/")
                    pdf_url = request.build_absolute_uri(os.path.join(media_url, cert.pdf)) if request else os.path.join(media_url, cert.pdf)
        except Exception:
            pdf_url = None

    return Response({
        "valid": True,
        "certificate_id": cert.id,
        "event_id": cert.registration.event.id,
        "event": cert.registration.event.title,
        "user": cert.registration.user.username if cert.registration.user else None,
        "issued_at": cert.issued_at,
        "pdf_url": pdf_url,
        "signed_url_expiry_seconds": signed_url_expiry,
    }, status=status.HTTP_200_OK)

