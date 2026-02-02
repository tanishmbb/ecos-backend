# core/supabase_client.py
# Supabase client for storage and analytics operations

import os
import logging
from functools import lru_cache

logger = logging.getLogger("cos")

# Lazy import to avoid errors if supabase is not installed
_supabase_client = None


def get_supabase_client():
    """
    Get the Supabase client instance (singleton pattern).
    Uses service_role key for admin access.
    """
    global _supabase_client

    if _supabase_client is None:
        try:
            from supabase import create_client, Client

            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

            if not url or not key:
                logger.warning("Supabase credentials not configured")
                return None

            _supabase_client = create_client(url, key)
            logger.info("Supabase client initialized")
        except ImportError:
            logger.warning("supabase package not installed")
            return None
        except Exception as e:
            logger.error(f"Failed to create Supabase client: {e}")
            return None

    return _supabase_client


def upload_certificate(user_id: str, cert_id: int, pdf_content: bytes) -> str | None:
    """
    Upload a certificate PDF to Supabase Storage.

    Args:
        user_id: The user's ID (for folder structure)
        cert_id: The certificate ID
        pdf_content: The PDF file content as bytes

    Returns:
        The storage path if successful, None otherwise
    """
    client = get_supabase_client()
    if not client:
        return None

    try:
        path = f"{user_id}/certificate_{cert_id}.pdf"

        # Upload to certificates bucket
        result = client.storage.from_("certificates").upload(
            path,
            pdf_content,
            file_options={"content-type": "application/pdf", "upsert": "true"}
        )

        logger.info(f"Uploaded certificate to storage: {path}")
        return path
    except Exception as e:
        logger.error(f"Failed to upload certificate: {e}")
        return None


def get_signed_url(path: str, expires_in: int = 600) -> str | None:
    """
    Generate a signed URL for a certificate in storage.

    Args:
        path: The storage path (e.g., "user_id/certificate_1.pdf")
        expires_in: URL expiry in seconds (default 10 minutes)

    Returns:
        The signed URL if successful, None otherwise
    """
    client = get_supabase_client()
    if not client:
        return None

    try:
        result = client.storage.from_("certificates").create_signed_url(
            path,
            expires_in
        )

        if result and "signedURL" in result:
            return result["signedURL"]
        return None
    except Exception as e:
        logger.error(f"Failed to generate signed URL: {e}")
        return None


def delete_certificate(path: str) -> bool:
    """
    Delete a certificate from storage.

    Args:
        path: The storage path

    Returns:
        True if successful, False otherwise
    """
    client = get_supabase_client()
    if not client:
        return False

    try:
        client.storage.from_("certificates").remove([path])
        logger.info(f"Deleted certificate from storage: {path}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete certificate: {e}")
        return False
