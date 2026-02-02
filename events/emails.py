# events/emails.py
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from events.models import EventRegistration, Announcement


def build_event_url(request, event):
    """
    Build an absolute URL to the event detail endpoint.
    Falls back to simple path if request is None.
    """
    try:
        path = reverse("event-detail", args=[event.id])
    except Exception:
        path = f"/api/v1/events/{event.id}/"
    if request is not None:
        return request.build_absolute_uri(path)
    return path


def build_certificate_verify_url(request, cert):
    """
    Build an absolute URL to the certificate verification endpoint.
    """
    event = cert.registration.event
    try:
        path = reverse("verify-certificate", args=[event.id, cert.cert_token])
    except Exception:
        path = f"/api/v1/events/{event.id}/certificate/verify/{cert.cert_token}/"
    if request is not None:
        return request.build_absolute_uri(path)
    return path


def send_registration_email(registration, request=None):
    """
    Send a simple registration confirmation email
    to the attendee.
    """
    user = registration.user
    event = registration.event

    if not getattr(user, "email", None):
        # No email set, nothing to send
        return

    subject = f"Registered for {event.title}"
    event_url = build_event_url(request, event)

    message = (
        f"Hi {user.username},\n\n"
        f"You have successfully registered for the event:\n"
        f"  {event.title}\n"
        f"  Venue: {event.venue}\n"
        f"  Starts: {event.start_time}\n\n"
        f"You can view the event details here:\n"
        f"{event_url}\n\n"
        f"Thank you,\n"
        f"COS Events"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[user.email],
        fail_silently=True,
    )


def send_certificate_email(certificate, request=None):
    """
    Send an email to the attendee when the certificate is issued.
    """
    reg = certificate.registration
    user = reg.user
    event = reg.event

    if not getattr(user, "email", None):
        return

    subject = f"Your certificate for {event.title} is ready"
    verify_url = build_certificate_verify_url(request, certificate)

    message = (
        f"Hi {user.username},\n\n"
        f"Your participation certificate for the event:\n"
        f"  {event.title}\n"
        f"is now issued.\n\n"
        f"You can verify and access your certificate here:\n"
        f"{verify_url}\n\n"
        f"If this wasn't you, you can ignore this email.\n\n"
        f"Best,\n"
        f"COS Events"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[user.email],
        fail_silently=True,
    )
def send_announcement_email(announcement, request=None):
    """
    Send email about a new announcement to all registrants of the event.
    Uses console backend in dev, so it's safe sync for now.
    """
    event = announcement.event

    # Get all registered users for this event
    regs = (
        EventRegistration.objects
        .select_related("user")
        .filter(event=event)
    )

    if not regs.exists():
        return

    subject = f"[Update] {event.title} - {announcement.title}"

    for reg in regs:
        user = reg.user
        if not getattr(user, "email", None):
            continue

        # Basic event link (reuse build_event_url)
        event_url = build_event_url(request, event)

        message = (
            f"Hi {user.username},\n\n"
            f"There is a new announcement for the event:\n"
            f"  {event.title}\n\n"
            f"Title: {announcement.title}\n"
            f"{announcement.body}\n\n"
            f"You can view the event here:\n"
            f"{event_url}\n\n"
            f"Best,\n"
            f"COS Events"
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[user.email],
            fail_silently=True,
        )
