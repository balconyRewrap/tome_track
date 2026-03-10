"""Validators for Django project."""
import re

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, UnidentifiedImageError
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.common.constants import ALLOWED_COVER_TYPES, COVER_MAX_SIZE_BYTES


def validate_model_cover_image(image: InMemoryUploadedFile) -> None:
    """Validate uploaded cover image for size, content type, and integrity.

    Used in models, not in serializers.

    Args:
        image: The uploaded image file to validate.

    Raises:
        django.core.exceptions.ValidationError: If the image fails any of the validation checks.
    """
    # Size check
    if image.size > COVER_MAX_SIZE_BYTES:
        raise ValidationError("File size must not exceed 5MB.")

    # Content type check
    content_type = getattr(image, 'content_type', None)
    if content_type not in ALLOWED_COVER_TYPES:
        raise ValidationError("Invalid image format. Allowed: JPEG, PNG, WEBP.")

    # Verify that file is image (using Pillow)
    try:
        img = Image.open(image)
        img.verify()
    except (UnidentifiedImageError, Exception) as e:
        raise ValidationError("File is not a valid image.") from e


def validate_serializer_name(value: str) -> str:
    """Validate the name field to ensure it does not contain invalid characters.

    Used in serializers, not in models.

    Args:
        value (str): The name of the book.

    Returns:
        str: The validated name of the book.

    Raises:
        rest_framework.exceptions.ValidationError: If the name contains invalid characters.
    """
    if not re.match(r"^[\w\s.,'()-:]+$", value):
        raise DRFValidationError('Name cannot contain invalid characters.')
    if re.search(r"[\x00-\x1F]", value):
        raise DRFValidationError("Name cannot contain control characters.")

    return value
