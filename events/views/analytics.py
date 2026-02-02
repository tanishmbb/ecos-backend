from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db.models import Count, Avg
from django.db.models.functions import TruncDate
from django.utils import timezone

from events.models import Event, EventRegistration, EventAttendance, EventFeedback
from events.throttles import CommunityEventCreateThrottle
from events.analytics import get_organizer_stats
from .generics import user_can_edit_event, get_active_community_id_for_user

class EventAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id):
        from events.models import Certificate
        from django.db.models import Sum

        try:
            event = Event.objects.get(pk=event_id)
        except Event.DoesNotExist:
            return Response({"error": "Event not found"}, status=404)

        if not user_can_edit_event(request.user, event):
            return Response({"error": "Not allowed"}, status=403)

        reg_qs = EventRegistration.objects.filter(event=event)
        total_registrations = reg_qs.count()

        # Guest metrics
        guest_data = reg_qs.aggregate(total_guests=Sum('guests_count'))
        total_guests = guest_data['total_guests'] or 0
        total_headcount = total_registrations + total_guests
        avg_guests_per_reg = round(total_guests / total_registrations, 2) if total_registrations > 0 else 0

        # Solo vs Group
        solo_registrations = reg_qs.filter(guests_count=0).count()
        group_registrations = reg_qs.filter(guests_count__gt=0).count()

        att_qs = EventAttendance.objects.filter(registration__event=event)
        checked_in = att_qs.filter(check_in__isnull=False).count()
        checked_out = att_qs.filter(check_out__isnull=False).count()

        total_attended = checked_in # Standard definition

        attendance_rate = 0
        if total_registrations > 0:
            attendance_rate = round((total_attended / total_registrations) * 100, 2)

        # No-show rate
        no_show_rate = round(100 - attendance_rate, 2) if total_registrations > 0 else 0

        # Certificate funnel
        certificate_count = Certificate.objects.filter(registration__event=event).count()
        certificate_rate = round((certificate_count / total_registrations) * 100, 2) if total_registrations > 0 else 0

        fb_qs = EventFeedback.objects.filter(event=event)
        feedback_count = fb_qs.count()
        avg_rating = fb_qs.aggregate(avg=Avg("rating"))["avg"]
        if avg_rating is not None:
            avg_rating = round(float(avg_rating), 2)

        rating_distribution = {str(star): fb_qs.filter(rating=star).count() for star in range(1, 6)}

        registration_timeline_qs = (
            reg_qs.annotate(date=TruncDate("registered_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )
        registration_timeline = [{"date": r["date"], "count": r["count"]} for r in registration_timeline_qs]

        data = {
            "event": event.title,
            "event_info": {
                "id": event.id,
                "title": event.title,
                "community_id": event.community_id,
                "capacity": event.capacity,
            },
            "registrations": {
                "total": total_registrations,
                "total_guests": total_guests,
                "total_headcount": total_headcount,
                "avg_guests_per_registration": avg_guests_per_reg,
                "solo_count": solo_registrations,
                "group_count": group_registrations,
                "timeline": registration_timeline,
            },
            "attendance": {
                "total_attended": total_attended,
                "checked_in": checked_in,
                "checked_out": checked_out,
                "attendance_rate": attendance_rate,
                "no_show_rate": no_show_rate,
                "conversion_rate": attendance_rate,
            },
            "certificates": {
                "issued": certificate_count,
                "issuance_rate": certificate_rate,
            },
            "feedback": {
                "count": feedback_count,
                "avg_rating": avg_rating,
                "rating_distribution": rating_distribution,
            },
        }
        return Response(data)


class OrganizerAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [CommunityEventCreateThrottle]

    def get(self, request):
        if getattr(request.user, "role", None) not in ["organizer", "admin"]:
            return Response({"error": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        community_id = request.query_params.get("community_id") or request.headers.get("X-Community-ID")
        if not community_id:
            community_id = get_active_community_id_for_user(request.user)

        stats = get_organizer_stats(request.user, community_id=community_id)

        return Response({
            "organizer": request.user.username,
            "stats": stats,
        }, status=status.HTTP_200_OK)


class OrganizerAnalyticsTrendsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if getattr(request.user, "role", None) not in ["organizer", "admin"]:
            return Response({"error": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        community_id = request.query_params.get("community_id") or request.headers.get("X-Community-ID")
        if not community_id:
             community_id = get_active_community_id_for_user(request.user)

        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)

        qs = EventRegistration.objects.filter(
            event__organizer=request.user,
            registered_at__gte=thirty_days_ago
        )

        if community_id and community_id != "undefined":
             qs = qs.filter(event__community_id=community_id)

        trends = (
            qs.annotate(date=TruncDate("registered_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

        data = [{"date": t["date"].strftime("%Y-%m-%d"), "count": t["count"]} for t in trends if t["date"]]
        return Response(data)
