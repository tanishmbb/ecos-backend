from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.http import HttpResponse # For CSV export

import csv
from events.models import Event, EventRegistration, EventAttendance
from events.serializers import RegistrationSerializer
from events.emails import send_registration_email
from .generics import api_error, user_can_edit_event

class RegisterEventView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, event_id):
        from django.db import transaction
        from django.db.models import Sum
        import logging

        logger = logging.getLogger('cos.events')

        # Check if already registered (outside transaction for fast fail)
        existing = EventRegistration.objects.filter(event_id=event_id, user=request.user).first()
        if existing:
            return Response(
                {"registered": True, "registration_id": existing.id},
                status=status.HTTP_409_CONFLICT,
            )

        guests_count = int(request.data.get("guests_count", 0))

        # Validate guests_count bounds
        if guests_count < 0 or guests_count > 10:
            return api_error("Guest count must be between 0 and 10", status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # Lock the event row to prevent race conditions
                event = Event.objects.select_for_update().get(pk=event_id)

                # Re-check registration inside transaction
                if EventRegistration.objects.filter(event=event, user=request.user).exists():
                    return Response(
                        {"registered": True, "message": "Already registered"},
                        status=status.HTTP_409_CONFLICT,
                    )

                # Capacity check inside transaction
                if event.capacity and event.capacity > 0:
                    current_count = EventRegistration.objects.filter(event=event).count()
                    current_guests = EventRegistration.objects.filter(event=event).aggregate(
                        Sum('guests_count')
                    )['guests_count__sum'] or 0
                    total_filled = current_count + current_guests
                    spots_needed = 1 + guests_count

                    if total_filled + spots_needed > event.capacity:
                        spots_left = max(0, event.capacity - total_filled)
                        logger.warning(
                            f"Registration failed: capacity exceeded for event {event_id}. "
                            f"Requested: {spots_needed}, Available: {spots_left}"
                        )
                        return api_error(
                            f"Event is full. Only {spots_left} spots left.",
                            status.HTTP_400_BAD_REQUEST
                        )

                # Create registration inside transaction
                reg = EventRegistration.objects.create(
                    event=event,
                    user=request.user,
                    guests_count=guests_count
                )

                # Create attendance record
                EventAttendance.objects.get_or_create(registration=reg)

                logger.info(f"Registration created: user={request.user.id}, event={event_id}, guests={guests_count}")

        except Event.DoesNotExist:
            return api_error("Event not found", status.HTTP_404_NOT_FOUND)

        # Send email outside transaction (non-critical)
        try:
            send_registration_email(reg, request=request)
        except Exception as e:
            logger.warning(f"Failed to send registration email for reg {reg.id}: {e}")

        serializer = RegistrationSerializer(reg)

        # Track analytics (non-critical)
        try:
            from core.analytics import track_registration
            track_registration(
                event_id=event.id,
                user_id=request.user.id,
                community_id=event.community_id if hasattr(event, 'community_id') else None
            )
        except Exception:
            pass

        return Response(serializer.data, status=status.HTTP_201_CREATED)



class CancelRegistrationView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, event_id):
        try:
            reg = EventRegistration.objects.get(event_id=event_id, user=request.user)
        except EventRegistration.DoesNotExist:
            return api_error("You are not registered for this event.", status.HTTP_400_BAD_REQUEST)

        # Soft delete (audit trail)
        reg.status = EventRegistration.STATUS_CANCELED
        reg.save(update_fields=['status'])

        # Also clear attendance if any (invalidating check-in)
        EventAttendance.objects.filter(registration=reg).update(check_in=None, check_out=None)

        return Response({"message": "Registration canceled"})


class EventRegistrationsView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id):
        try:
            event = Event.objects.get(pk=event_id)
        except Event.DoesNotExist:
            return api_error("Event not found", status.HTTP_404_NOT_FOUND)

        if not user_can_edit_event(request.user, event):
            return api_error("You do not have permission to view registrations for this event.", status.HTTP_403_FORBIDDEN)

        # Optimize query: load user and attendance (qr code)
        regs = (
            EventRegistration.objects
            .filter(event=event)
            .exclude(status=EventRegistration.STATUS_CANCELED) # Hide canceled? Or show? Usually organizers want to see valid ones.
                                                               # Let's show all but maybe filter in UI. Data consistency -> return all.
                                                               # Actually, standard is to show active. Let's return all so organizer knows.
            .select_related('user', 'attendance')
            .order_by('-registered_at')
        )

        # Pagination
        from rest_framework.pagination import LimitOffsetPagination
        paginator = LimitOffsetPagination()
        result_page = paginator.paginate_queryset(regs, request)
        serializer = RegistrationSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)


class EventRegistrationUpdateView(APIView):
    """
    PATCH /api/events/registrations/<reg_id>/
    Body: { "status": "approved" | "rejected" | "waitlisted" }
    """
    authentication_classes = [JWTAuthentication, SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, reg_id):
        reg = get_object_or_404(EventRegistration, pk=reg_id)
        event = reg.event

        if not user_can_edit_event(request.user, event):
             return api_error("You do not have permission to manage registrations for this event.", status.HTTP_403_FORBIDDEN)

        new_status = request.data.get("status")
        if new_status not in dict(EventRegistration.STATUS_CHOICES):
            return api_error("Invalid status", status.HTTP_400_BAD_REQUEST)

        reg.status = new_status
        if new_status == EventRegistration.STATUS_APPROVED:
            reg.approved = True
        elif new_status == EventRegistration.STATUS_REJECTED:
            reg.approved = False

        reg.save()

        if new_status == EventRegistration.STATUS_APPROVED:
             EventAttendance.objects.get_or_create(registration=reg)

        return Response(RegistrationSerializer(reg).data)


class EventRegistrationExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id):
        event = get_object_or_404(Event, pk=event_id)

        if not user_can_edit_event(request.user, event):
             return api_error("Permission denied", status.HTTP_403_FORBIDDEN)

        registrations = EventRegistration.objects.filter(event=event).select_related('user', 'attendance')

        response = HttpResponse(
            content_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="registrations_{event_id}.csv"'},
        )

        writer = csv.writer(response)
        # Enhanced headers as per Audit requirement
        writer.writerow(["ID", "Username", "Email", "Status", "Registered At", "Payment Status", "Guests", "Headcount", "Check-In Time"])

        for reg in registrations:
            check_in = "N/A"
            if hasattr(reg, 'attendance') and reg.attendance.check_in:
                check_in = reg.attendance.check_in.strftime("%Y-%m-%d %H:%M:%S")

            writer.writerow([
                reg.id,
                reg.user.username,
                reg.user.email,
                reg.status,
                reg.registered_at.strftime("%Y-%m-%d %H:%M:%S"),
                reg.payment_status,
                reg.guests_count,
                1 + reg.guests_count,
                check_in
            ])

        return response


class EventRegistrationStatusView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id):
        reg = EventRegistration.objects.filter(
            event_id=event_id,
            user=request.user
        ).first()

        if not reg:
            return Response({"registered": False}, status=200)

        return Response({
            "registered": True,
            "registration_id": reg.id,
        }, status=200)
