# authx/urls.py
from django.urls import path
from .views import SignupView, LoginView,MeView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,

)

urlpatterns = [
    # Your existing views
    path("signup/", SignupView.as_view(), name="signup"),
    path("login/", LoginView.as_view(), name="login"),
    path("me/", MeView.as_view()),
    # New JWT views
    path("jwt/login/", TokenObtainPairView.as_view(), name="jwt-login"),
    path("jwt/refresh/", TokenRefreshView.as_view(), name="jwt-refresh"),
    path("jwt/verify/", TokenVerifyView.as_view(), name="jwt-verify"),
]
