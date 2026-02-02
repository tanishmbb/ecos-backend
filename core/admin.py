from django.contrib import admin
from .models import Community, CommunityMembership, CommunityInvite, FeedItem, Announcement

@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'created_by', 'created_at')
    search_fields = ('name', 'slug', 'description')
    list_filter = ('is_active', 'created_at')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(CommunityMembership)
class CommunityMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'community', 'role', 'is_active', 'is_default', 'joined_at')
    list_filter = ('role', 'is_active', 'is_default', 'community')
    search_fields = ('user__username', 'community__name')

@admin.register(CommunityInvite)
class CommunityInviteAdmin(admin.ModelAdmin):
    list_display = ('community', 'token', 'role', 'used_count', 'max_uses', 'is_active', 'expires_at')
    list_filter = ('is_active', 'role', 'community')
    search_fields = ('token', 'community__name')

@admin.register(FeedItem)
class FeedItemAdmin(admin.ModelAdmin):
    list_display = ('type', 'created_at', 'event', 'announcement', 'certificate')
    list_filter = ('type', 'created_at')

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'organizer', 'event', 'created_at')
    search_fields = ('title', 'message')
    list_filter = ('created_at',)
