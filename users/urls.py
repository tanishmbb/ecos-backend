# users/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProfileViewSet, UserViewSet, GoogleLoginView

router = DefaultRouter()
router.register(r'profile', ProfileViewSet, basename='profile')
router.register(r'', UserViewSet, basename='user')

urlpatterns = [
    path('', include(router.urls)),
    path('google/', GoogleLoginView.as_view(), name='google_login'),
]
