from django.core.exceptions import ValidationError
from apps.common.validators import validate_model_cover_image, validate_serializer_name
import pytest

def test_validate_cover_image_too_large():
    image = type('Fake', (), {'size': 6 * 1024 * 1024, 'content_type': 'image/jpeg', 'read': lambda self: b''})()
    with pytest.raises(ValidationError):
        validate_model_cover_image(image)  # pyright: ignore[reportArgumentType]

def test_validate_cover_image_bad_type():
    image = type('Fake', (), {'size': 100, 'content_type': 'image/gif', 'read': lambda self: b''})()
    with pytest.raises(ValidationError):
        validate_model_cover_image(image)  # pyright: ignore[reportArgumentType]

def test_validate_cover_image_not_image(mocker):
    image = type('Fake', (), {'size': 100, 'content_type': 'image/jpeg', 'read': lambda self: b''})()
    mocker.patch('PIL.Image.open', side_effect=Exception)
    with pytest.raises(ValidationError):
        validate_model_cover_image(image)  # pyright: ignore[reportArgumentType]

def test_validate_cover_image_valid(mocker):
    image = type('Fake', (), {'size': 100, 'content_type': 'image/jpeg', 'read': lambda self: b''})()
    mock_img = mocker.Mock()
    mocker.patch('PIL.Image.open', return_value=mock_img)
    mock_img.verify.return_value = None
    validate_model_cover_image(image)  # pyright: ignore[reportArgumentType]

def test_validate_serializer_name_valid():
    assert validate_serializer_name("Valid Book Name 123.,'()-:?!—" ) == "Valid Book Name 123.,'()-:?!"

def test_validate_serializer_name_invalid_characters():
    with pytest.raises(Exception):
        validate_serializer_name("Invalid@Name!")

def test_validate_serializer_name_control_characters():
    with pytest.raises(Exception):
        validate_serializer_name("Hello\tWorld")

def test_validate_serializer_name_empty():
    with pytest.raises(Exception):
        validate_serializer_name("   ")

