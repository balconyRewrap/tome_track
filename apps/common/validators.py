"""Validators for Django project."""
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, UnidentifiedImageError

from apps.common.constants import ALLOWED_COVER_TYPES, COVER_MAX_SIZE_BYTES


def validate_cover_image(image: InMemoryUploadedFile) -> None:
    """Validate uploaded cover image for size, content type, and integrity.

    Args:
        image: The uploaded image file to validate.

    Raises:
        ValidationError: If the image fails any of the validation checks.
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
