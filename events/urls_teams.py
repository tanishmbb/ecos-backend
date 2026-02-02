# events/urls_teams.py - Separate URL configuration for teams API

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views.teams import EventTeamViewSet

router = DefaultRouter()
router.register(r'', EventTeamViewSet, basename='event-teams')

urlpatterns = router.urls
