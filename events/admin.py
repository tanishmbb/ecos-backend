from django.contrib import admin
from .models import (
    Event, EventRegistration, EventAttendance, Certificate,
    ScanLog, Announcement, EventFeedback, EventTeamMember
)

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'community', 'organizer', 'start_time', 'is_public')
    list_filter = ('status', 'is_public', 'community', 'start_time')
    search_fields = ('title', 'description', 'organizer__username')
    date_hierarchy = 'start_time'

@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'status', 'guests_count', 'registered_at')
    list_filter = ('status', 'event__community')
    search_fields = ('user__username', 'event__title')

@admin.register(EventAttendance)
class EventAttendanceAdmin(admin.ModelAdmin):
    list_display = ('registration', 'check_in', 'check_out', 'qr_code')
    search_fields = ('registration__user__username', 'qr_code')
    list_filter = ('check_in',)

@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ('registration', 'issued_at', 'cert_token')
    search_fields = ('registration__user__username', 'cert_token')

@admin.register(ScanLog)
class ScanLogAdmin(admin.ModelAdmin):
    list_display = ('scanned_by', 'action', 'event', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('scanned_by__username', 'qr_code')

@admin.register(Announcement)
class EventAnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'event', 'posted_by', 'is_important', 'created_at')
    list_filter = ('is_important', 'created_at')
    search_fields = ('title', 'body', 'event__title')

@admin.register(EventFeedback)
class EventFeedbackAdmin(admin.ModelAdmin):
    list_display = ('event', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('comment', 'event__title', 'user__username')

@admin.register(EventTeamMember)
class EventTeamMemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'role', 'is_active')
    list_filter = ('role', 'is_active')
    search_fields = ('user__username', 'event__title')
