# core/supabase_auth.py
# Custom DRF authentication class to verify Supabase JWTs

import os
import logging
import jwt
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger("cos")

User = get_user_model()


class SupabaseJWTAuthentication(BaseAuthentication):
    """
    Custom authentication class that validates Supabase JWTs.

    This authenticator:
    1. Extracts the JWT from the Authorization header
    2. Verifies the token signature using the Supabase JWT secret
    3. Looks up or creates a Django user based on the Supabase user ID
    """

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return None  # Let other auth backends handle it

        token = auth_header.split(" ")[1]

        try:
            # Decode the JWT
            supabase_jwt_secret = os.environ.get("SUPABASE_JWT_SECRET")

            if not supabase_jwt_secret:
                logger.warning("SUPABASE_JWT_SECRET not configured")
                return None

            # Supabase uses HS256 by default
            payload = jwt.decode(
                token,
                supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )

            # Get user info from token
            supabase_user_id = payload.get("sub")
            email = payload.get("email")

            if not supabase_user_id:
                raise AuthenticationFailed("Invalid token: missing user ID")

            # Get or create Django user
            user = self._get_or_create_user(supabase_user_id, email, payload)

            return (user, payload)

        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed("Token has expired")
        except jwt.InvalidTokenError as e:
            logger.debug(f"Invalid Supabase token: {e}")
            return None  # Let other auth backends try

    def _get_or_create_user(self, supabase_user_id: str, email: str, payload: dict):
        """
        Get or create a Django user based on Supabase user ID.

        We store the Supabase user ID in a way that allows mapping.
        For now, we use email as the primary identifier.
        """
        if not email:
            raise AuthenticationFailed("Token missing email claim")

        try:
            # Try to find user by email
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Create a new user
            username = email.split("@")[0]
            # Ensure unique username
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1

            user = User.objects.create(
                username=username,
                email=email,
                # Password is not used for Supabase auth
            )
            logger.info(f"Created new user from Supabase: {email}")

        return user
