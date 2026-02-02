# cos-backend/events/sanitizers.py
"""
Input sanitization and validation for e-COS.

All user-generated content should pass through these functions
before being stored or rendered.
"""
import re
from decimal import Decimal, InvalidOperation
from typing import Optional

# Try to import bleach, fall back to basic sanitization if unavailable
try:
    import bleach
    HAS_BLEACH = True
except ImportError:
    HAS_BLEACH = False


# Allowed HTML tags for rich text (announcements, descriptions)
ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 'a', 'ul', 'ol', 'li',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'code', 'pre'
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
}


def sanitize_text(text: Optional[str], max_length: Optional[int] = None, strip: bool = True) -> str:
    """
    Sanitize plain text input.

    - Strips leading/trailing whitespace
    - Removes control characters
    - Enforces maximum length
    - Returns empty string for None input
    """
    if text is None:
        return ""

    if strip:
        text = text.strip()

    # Remove control characters except newlines and tabs
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    if max_length and len(text) > max_length:
        text = text[:max_length]

    return text


def sanitize_html(html: Optional[str], max_length: Optional[int] = None) -> str:
    """
    Sanitize HTML content, removing dangerous elements.

    Uses bleach if available, otherwise falls back to stripping all tags.
    """
    if html is None:
        return ""

    html = html.strip()

    if HAS_BLEACH:
        # Use bleach to clean HTML
        clean = bleach.clean(
            html,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            strip=True
        )
    else:
        # Fallback: strip all HTML tags
        clean = re.sub(r'<[^>]+>', '', html)

    if max_length and len(clean) > max_length:
        clean = clean[:max_length]

    return clean


def sanitize_title(title: Optional[str]) -> str:
    """
    Sanitize event/announcement titles.

    - Max 255 characters
    - No HTML
    - Single line (no newlines)
    """
    text = sanitize_text(title, max_length=255)
    # Replace newlines with spaces
    text = re.sub(r'[\r\n]+', ' ', text)
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    return text


def sanitize_description(description: Optional[str]) -> str:
    """
    Sanitize event/announcement descriptions.

    - Max 10000 characters
    - HTML sanitized (if bleach available)
    """
    return sanitize_html(description, max_length=10000)


# ─────────────────────────────────────────────────────────────
# Numeric Validators
# ─────────────────────────────────────────────────────────────

class ValidationError(Exception):
    """Raised when validation fails."""
    pass


def validate_capacity(value, min_value: int = 0, max_value: int = 100000) -> int:
    """
    Validate event capacity.

    - Must be an integer
    - Must be between min_value and max_value
    - 0 means unlimited
    """
    try:
        capacity = int(value)
    except (TypeError, ValueError):
        raise ValidationError("Capacity must be a valid integer")

    if capacity < min_value:
        raise ValidationError(f"Capacity must be at least {min_value}")

    if capacity > max_value:
        raise ValidationError(f"Capacity cannot exceed {max_value}")

    return capacity


def validate_price(value, min_value: Decimal = Decimal('0'), max_value: Decimal = Decimal('999999.99')) -> Decimal:
    """
    Validate event price.

    - Must be a valid decimal
    - Must be non-negative
    - Maximum 2 decimal places
    """
    try:
        if isinstance(value, str):
            value = value.strip()
            if value == '':
                value = '0'
        price = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        raise ValidationError("Price must be a valid number")

    if price < min_value:
        raise ValidationError(f"Price must be at least {min_value}")

    if price > max_value:
        raise ValidationError(f"Price cannot exceed {max_value}")

    # Round to 2 decimal places
    price = price.quantize(Decimal('0.01'))

    return price


def validate_guests(value, min_value: int = 0, max_value: int = 10) -> int:
    """
    Validate guest count.

    - Must be an integer
    - Must be between min_value and max_value
    """
    try:
        guests = int(value)
    except (TypeError, ValueError):
        raise ValidationError("Guest count must be a valid integer")

    if guests < min_value:
        raise ValidationError(f"Guest count must be at least {min_value}")

    if guests > max_value:
        raise ValidationError(f"Guest count cannot exceed {max_value}")

    return guests


def validate_email(email: Optional[str]) -> str:
    """
    Basic email validation.
    """
    if not email:
        raise ValidationError("Email is required")

    email = sanitize_text(email, max_length=254)

    # Basic email pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        raise ValidationError("Invalid email format")

    return email.lower()


def validate_url(url: Optional[str], required: bool = False) -> Optional[str]:
    """
    Validate and sanitize URLs.
    """
    if not url:
        if required:
            raise ValidationError("URL is required")
        return None

    url = sanitize_text(url, max_length=2048)

    # Basic URL pattern
    pattern = r'^https?://[^\s<>"{}|\\^`\[\]]+$'
    if not re.match(pattern, url):
        raise ValidationError("Invalid URL format")

    return url
