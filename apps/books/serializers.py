"""Serializers for Books application."""
import logging
from typing import Any, cast

import bleach
from django.utils.text import slugify
from drf_spectacular.utils import extend_schema_field
from parler_rest.serializers import TranslatableModelSerializer, TranslatedFieldsField
from rest_framework import serializers

from apps.books.models import AUTHOR_MAX_COUNT, TAG_MAX_COUNT, TAG_TRANSLATION_LANGUAGES, Author, Book, BookType, Tag
from apps.common.validators import validate_serializer_name

logger = logging.getLogger(__name__)


# Annotating the *class* (not the instance) is the only reliable way to override
# drf-spectacular's built-in ImageField mapping, which ignores instance-level annotations.
@extend_schema_field({'type': 'string', 'format': 'binary'})
class CoverImageField(serializers.ImageField):
    """Class for schema override of cover image field in BookSerializer."""


class AuthorSerializer(serializers.ModelSerializer):
    """Serializer for Author model."""

    name = serializers.CharField(min_length=2, max_length=255, validators=[validate_serializer_name])
    class Meta:  # noqa: D106
        model = Author
        fields = ['id', 'name']

    def validate_name(self, value: str) -> str:
        """Validate that the name does not contain control characters.

        Args:
            value (str): The name to validate.

        Raises:
            serializers.ValidationError: If the name contains control characters.

        Returns:
            str: The validated name.
        """
        qs = Author.objects.filter(name=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('An author with this name already exists.')
        return value


class TagSerializer(TranslatableModelSerializer):
    """Serializer for Tag model with explicit translations payload."""

    slug = serializers.SlugField(read_only=True)
    translations = TranslatedFieldsField(shared_model=Tag)

    class Meta:  # noqa: D106
        model = Tag
        fields = ['id', 'slug', 'translations']

    def validate_translations(self, value: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
        """Validate translated names for required languages.

        Args:
            value (dict[str, dict[str, str]]): Translation payload by language code.

        Raises:
            serializers.ValidationError: If payload is malformed or missing required languages.

        Returns:
            dict[str, dict[str, str]]: Normalized and validated translations.
        """
        if not isinstance(value, dict) or not value:
            raise serializers.ValidationError('translations must be a non-empty object.')

        allowed_languages = set(TAG_TRANSLATION_LANGUAGES)
        provided_languages = set(value)
        unknown_languages = provided_languages - allowed_languages
        if unknown_languages:
            raise serializers.ValidationError(
                f'Unsupported languages: {", ".join(sorted(unknown_languages))}. '
                f'Allowed languages: {", ".join(TAG_TRANSLATION_LANGUAGES)}.',
            )

        if not self.partial:
            missing_languages = allowed_languages - provided_languages
            if missing_languages:
                raise serializers.ValidationError(
                    f'Missing required languages: {", ".join(sorted(missing_languages))}.',
                )

        for language_code, payload in value.items():
            if not isinstance(payload, dict):
                raise serializers.ValidationError({language_code: 'Translation value must be an object.'})

            raw_name = payload.get('name')
            if raw_name is None:
                raise serializers.ValidationError({language_code: {'name': 'This field is required.'}})

            payload['name'] = validate_serializer_name(str(raw_name))
            duplicated = Tag.objects.filter(
                translations__language_code=language_code,
                translations__name=payload['name'],
            )
            if self.instance:
                duplicated = duplicated.exclude(pk=self.instance.pk)
            if duplicated.exists():
                raise serializers.ValidationError(
                    {language_code: {'name': 'A tag with this name already exists for this language.'}},
                )

        return value

    def to_representation(self, instance: Tag) -> dict:
        """Return all supported languages even if a translation is missing.

        Returns:
            dict: Serialized tag payload with ru, en and de language keys.
        """
        data = super().to_representation(instance)
        existing_translations = data.get('translations', {})
        data['translations'] = {
            language_code: {'name': existing_translations.get(language_code, {}).get('name')}
            for language_code in TAG_TRANSLATION_LANGUAGES
        }
        return data

    def save(self, **kwargs: Any) -> Tag:
        """Save tag and derive slug from preferred translation when needed.

        Returns:
            Tag: Saved tag instance.
        """
        validated_data = cast('dict[str, dict[str, dict[str, str]]]', self.validated_data)
        translations = validated_data.get('translations', {})
        slug_source = (
            translations.get('en', {}).get('name')
            or translations.get('ru', {}).get('name')
            or translations.get('de', {}).get('name')
        )
        if slug_source and not self.instance and not kwargs.get('slug'):
            kwargs['slug'] = slugify(slug_source)
        return cast('Tag', super().save(**kwargs))


class BookSerializer(serializers.ModelSerializer):
    """Serializer for Book model with business validation."""

    cover = CoverImageField(use_url=True, required=False, allow_null=True)
    average_rating = serializers.FloatField(read_only=True)  # annotated
    ratings_count = serializers.IntegerField(read_only=True)  # annotated
    authors = AuthorSerializer(many=True, read_only=True)
    class Meta:  # noqa: D106
        model = Book
        fields = [
            'id',
            'title',
            'title_en',
            'cover',
            'authors',
            'description',
            'tags',
            'book_type',
            'country',
            'pages_total',
            'chapters_total',
            'edition',
            'parent_book',
            'user',
            'average_rating',
            'ratings_count',
            'created_at',
            'updated_at',
        ]
        extra_kwargs = {
            'title': {'required': True},
            'title_en': {'required': True},
            'authors': {'required': True},
            'book_type': {'required': True},
            'cover': {'required': False},
            'description': {'required': False, 'allow_blank': True},
            'tags': {'required': False},
            'country': {'required': False},
            'pages_total': {'required': False},
            'chapters_total': {'required': False},
            'edition': {'required': False, 'allow_blank': True},
            'parent_book': {'required': False, 'allow_null': True},
            'id': {'read_only': True},
            'user': {'read_only': True},
            'average_rating': {'read_only': True},
            'ratings_count': {'read_only': True},
            'created_at': {'read_only': True},
            'updated_at': {'read_only': True},
        }


class BookWriteSerializer(BookSerializer):
    """Serializer for writing Book — cover rendered as binary upload in Swagger.

    The viewset uses this class for create/update operations via
    ``get_serializer_class`` (see ``books.views.BookViewSet``).  It also
    contains a couple of helpers so that the horrible string that Swagger
    sends when you tick **Send empty value** for the ``tags`` list is
    converted into a real empty list instead of blowing up with
    ``Incorrect type. Expected pk value, received str.``.
    """

    # drf-spectacular maps use_url=False → format: binary → file upload widget in Swagger.
    # At runtime DRF still saves the uploaded file normally regardless of this flag.
    title = serializers.CharField(validators=[validate_serializer_name])
    title_en = serializers.CharField(validators=[validate_serializer_name])
    cover = serializers.ImageField(use_url=False, required=False, allow_null=True)

    # override the automatically-generated field so we can intercept
    # the pathological values that the Swagger UI ships when the user
    # checks **Send empty value** on a list field.  We intentionally
    # subclass ``PrimaryKeyRelatedField`` rather than use the default
    # model-generated one so we can tweak the behaviour later if needed.
    tags = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all(),
        required=False,
        allow_empty=True,
    )
    authors = serializers.PrimaryKeyRelatedField(many=True, queryset=Author.objects.all(), required=True)

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        """Log and normalize raw tags payload before DRF field conversion.

        Args:
            data (Any): Raw incoming request payload.

        Raises:
            serializers.ValidationError: If DRF field validation fails.

        Returns:
            dict[str, Any]: Parsed serializer payload.
        """
        raw_tags = data.get('tags') if hasattr(data, 'get') else None
        raw_tags_list = data.getlist('tags') if hasattr(data, 'getlist') else None
        logger.warning('[BookWriteSerializer.to_internal_value] raw tags = %r', raw_tags)
        logger.warning('[BookWriteSerializer.to_internal_value] raw tags getlist = %r', raw_tags_list)

        normalized_data = data
        mutable_data = data.copy() if hasattr(data, 'copy') else data

        tag_tokens: list[Any] = []

        # DRF can pass tags as a list (JSON body) or as query params (getlist).
        # We normalize both formats to an iterable of values.
        if raw_tags_list is not None:
            raw_tag_values = raw_tags_list
        elif isinstance(raw_tags, list):
            raw_tag_values = raw_tags
        elif raw_tags is not None:
            raw_tag_values = [raw_tags]
        else:
            raw_tag_values = None

        if raw_tag_values is not None:
            for raw_value in raw_tag_values:
                if isinstance(raw_value, str) and ',' in raw_value:
                    tag_tokens.extend(part.strip() for part in raw_value.split(',') if part.strip())
                elif raw_value not in {None, ''}:
                    tag_tokens.append(raw_value)

            coerced_tag_ids: list[int] = []
            for token in tag_tokens:
                try:
                    coerced_tag_ids.append(int(token))
                except (TypeError, ValueError) as exc:
                    raise serializers.ValidationError({'tags': [f'Invalid tag id: {token!r}.']}) from exc

            if hasattr(mutable_data, 'setlist'):
                mutable_data.setlist('tags', coerced_tag_ids)
                logger.warning(
                    '[BookWriteSerializer.to_internal_value] normalized tags getlist = %r',
                    mutable_data.getlist('tags'),
                )
            elif isinstance(mutable_data, dict):
                mutable_data['tags'] = coerced_tag_ids
                logger.warning(
                    '[BookWriteSerializer.to_internal_value] normalized tags list = %r',
                    mutable_data.get('tags'),
                )
            normalized_data = mutable_data

        try:
            validated = super().to_internal_value(normalized_data)
            logger.warning('[BookWriteSerializer.to_internal_value] parsed tags = %r', validated.get('tags'))
            return cast('dict[str, Any]', validated)
        except serializers.ValidationError as exc:
            logger.warning('[BookWriteSerializer.to_internal_value] validation error detail = %r', exc.detail)
            raise

    def validate(self, attrs: dict) -> dict:
        """Validate cross-field business rules.

        Raises:
            serializers.ValidationError: If any business rule is violated.

        Returns:
            dict: The validated attributes.
        """
        authors = attrs.get('authors')
        tags = attrs.get('tags', [])
        logger.warning('[BookWriteSerializer.validate] tags = %r', tags)
        book_type = attrs.get('book_type', BookType.BOOK)
        pages_total = attrs.get('pages_total')
        chapters_total = attrs.get('chapters_total')
        if authors is not None and len(authors) > AUTHOR_MAX_COUNT:
            raise serializers.ValidationError(
                {'authors': f'A book can have at most {AUTHOR_MAX_COUNT} authors.'},
            )

        if len(tags) > TAG_MAX_COUNT:
            raise serializers.ValidationError(
                {'tags': f'A book can have at most {TAG_MAX_COUNT} tags.'},
            )
        if not self.partial:
            if book_type == BookType.BOOK and not pages_total:
                raise serializers.ValidationError(
                    {'pages_total': 'pages_total is required for book type "book".'},
                )

            if book_type == BookType.COMIC and not chapters_total:
                raise serializers.ValidationError(
                    {'chapters_total': 'chapters_total is required for book type "comic".'},
                )
        else:
            existing_pages = getattr(self.instance, 'pages_total', None)
            existing_chapters = getattr(self.instance, 'chapters_total', None)
            effective_pages = attrs.get('pages_total', existing_pages)
            effective_chapters = attrs.get('chapters_total', existing_chapters)
            if book_type == BookType.BOOK and not effective_pages:
                raise serializers.ValidationError(
                    {'pages_total': 'pages_total is required for book type "book".'},
                )
            if book_type == BookType.COMIC and not effective_chapters:
                raise serializers.ValidationError(
                    {'chapters_total': 'chapters_total is required for book type "comic".'},
                )

        return attrs

    def validate_tags(self, value: list[Tag]) -> list[Tag]:  # noqa: PLR6301
        """Log parsed tags payload for write serializer debugging.

        Args:
            value (list[Tag]): Parsed list of tag instances.

        Returns:
            list[Tag]: Unchanged parsed tags list.
        """
        logger.warning('[BookWriteSerializer.validate_tags] value = %r', value)
        return value

    def validate_description(self, value: str) -> str:  # noqa: PLR6301
        """Validate that the description does not contain control characters.

        Args:
            value (str): The description to validate.

        Returns:
            str: The validated description.
        """
        return bleach.clean(value, tags=['b', 'i', 'p'], strip=True)
