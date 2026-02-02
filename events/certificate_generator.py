# events/certificate_generator.py

import os
import uuid
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors


def _hex_to_color(hex_str, default=colors.HexColor("#2c3e50")):
    """
    Safely convert a HEX string (#RRGGBB) to a reportlab Color.
    """
    try:
        return colors.HexColor(hex_str)
    except Exception:
        return default


def _safe_image_reader(field_file):
    """
    Try to build an ImageReader from a FileField (logo/template).
    Works only if .path is available (local storage). If using S3-only
    without local paths, this will just return None and we skip images.
    """
    try:
        if field_file and hasattr(field_file, "path"):
            return ImageReader(field_file.path)
    except Exception:
        return None
    return None


def generate_certificate_pdf(user, event, certificate_id=None):
    """
    Generate a PDF certificate and save it using Django's default storage.

    Uses community branding if available:
    - community.primary_color as accent/border
    - community.certificate_template as background image
    - community.logo in the corner

    Returns the storage path (e.g. 'certificates/xyz.pdf') which can be
    assigned directly to a FileField.

    This function is compatible with both local filesystem and S3 storage.
    """
    buffer = BytesIO()

    # Use landscape A4 for a more certificate-like layout
    page_size = landscape(A4)
    p = canvas.Canvas(buffer, pagesize=page_size)
    width, height = page_size

    community = getattr(event, "community", None)

    # ---------- Accent color ----------
    default_accent = colors.HexColor("#2c3e50")
    accent_hex = "#2c3e50"
    if community and getattr(community, "primary_color", None):
        accent_hex = community.primary_color.strip()
    accent_color = _hex_to_color(accent_hex, default=default_accent)

    # ---------- Optional background template ----------
    bg_reader = None
    if community and getattr(community, "certificate_template", None):
        bg_reader = _safe_image_reader(community.certificate_template)

    if bg_reader is not None:
        try:
            p.drawImage(
                bg_reader,
                0,
                0,
                width=width,
                height=height,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            # If anything fails, just continue with a plain background
            pass

    # ---------- Border ----------
    p.setStrokeColor(accent_color)
    p.setLineWidth(4)
    margin = 30
    p.rect(
        margin,
        margin,
        width - 2 * margin,
        height - 2 * margin,
        stroke=1,
        fill=0,
    )

    # ---------- Title ----------
    p.setFillColor(accent_color)
    p.setFont("Helvetica-Bold", 36)
    title_text = "Certificate of Participation"
    p.drawCentredString(width / 2.0, height - 120, title_text)

    # ---------- Body text ----------
    p.setFillColor(colors.black)

    user_display = user.get_full_name() or user.username
    name_text = f"This is to certify that {user_display}"
    event_text = f"has successfully participated in the event \"{event.title}\"."

    p.setFont("Helvetica", 18)
    p.drawCentredString(width / 2.0, height - 200, name_text)
    p.drawCentredString(width / 2.0, height - 230, event_text)

    # ---------- Footer ----------
    community_name = None
    if community:
        community_name = getattr(community, "name", None)
    if not community_name:
        community_name = "COS Community"

    organizer_name = getattr(event.organizer, "username", "Organizer")

    p.setFont("Helvetica-Oblique", 12)
    footer_text_left = f"Issued by {community_name}"
    footer_text_right = f"Event Organizer: {organizer_name}"

    p.drawString(margin + 10, 80, footer_text_left)
    p.drawRightString(width - margin - 10, 80, footer_text_right)

    # ---------- Optional logo ----------
    logo_reader = None
    if community and getattr(community, "logo", None):
        logo_reader = _safe_image_reader(community.logo)

    if logo_reader is not None:
        try:
            logo_width = 120
            logo_height = 120
            p.drawImage(
                logo_reader,
                width - logo_width - 60,
                height - logo_height - 80,
                width=logo_width,
                height=logo_height,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            # If logo fails, ignore
            pass

    p.showPage()
    p.save()

    # Get bytes and save via default_storage
    buffer.seek(0)
    pdf_bytes = buffer.getvalue()

    # Build a reasonably unique filename
    if certificate_id is not None:
        base_name = f"certificate_{certificate_id}"
    else:
        base_name = f"certificate_{user.id}_{event.id}_{uuid.uuid4().hex}"

    filename = os.path.join("certificates", f"{base_name}.pdf").replace("\\", "/")

    saved_path = default_storage.save(filename, ContentFile(pdf_bytes))

    # Also upload to Supabase Storage for signed URL access
    try:
        from core.supabase_client import upload_certificate
        supabase_path = upload_certificate(str(user.id), certificate_id or 0, pdf_bytes)
        if supabase_path:
            import logging
            logging.getLogger("cos").info(f"Certificate uploaded to Supabase: {supabase_path}")
    except Exception as e:
        import logging
        logging.getLogger("cos").warning(f"Supabase upload failed (non-critical): {e}")

    return saved_path

