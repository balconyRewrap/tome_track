"""Tests for automatic cover conversion to WebP."""
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.books.models import Book

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def temporary_media_root(tmp_path, settings) -> None:
    """Store uploaded files in an isolated temporary media directory."""
    settings.MEDIA_ROOT = tmp_path


def _image_bytes(fmt: str) -> bytes:
    """Create a tiny in-memory image for upload tests."""
    output = BytesIO()
    Image.new('RGB', (16, 16), color='red').save(output, format=fmt)
    return output.getvalue()


def test_book_cover_is_converted_to_webp_on_save() -> None:
    """PNG cover is converted to WebP when the model is saved."""
    uploaded_cover = SimpleUploadedFile(
        'cover.png',
        _image_bytes('PNG'),
        content_type='image/png',
    )

    book = Book.objects.create(
        title='Book With PNG Cover',
        title_en='Book With PNG Cover',
        description='Test',
        book_type='book',
        pages_total=10,
        cover=uploaded_cover,
    )

    assert book.cover.name.lower().endswith('.webp')
    book.cover.open('rb')
    with Image.open(book.cover) as image:
        assert image.format == 'WEBP'


def test_book_cover_with_webp_extension_is_not_renamed() -> None:
    """Already-WebP uploads keep WebP extension after save."""
    uploaded_cover = SimpleUploadedFile(
        'cover.webp',
        _image_bytes('WEBP'),
        content_type='image/webp',
    )

    book = Book.objects.create(
        title='Book With WebP Cover',
        title_en='Book With WebP Cover',
        description='Test',
        book_type='book',
        pages_total=10,
        cover=uploaded_cover,
    )

    assert book.cover.name.lower().endswith('.webp')
