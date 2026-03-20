"""Serializers for Books application."""
import logging
from typing import Any, cast

import bleach
from django.http import QueryDict
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


class TagTranslationsRuSerializer(serializers.Serializer):
    """Tag translations payload for Russian locale."""

    name = serializers.CharField(max_length=100, validators=[validate_serializer_name])


class TagTranslationsEnSerializer(serializers.Serializer):
    """Tag translations payload for English locale."""

    name = serializers.CharField(max_length=100, validators=[validate_serializer_name])


class TagTranslationsDeSerializer(serializers.Serializer):
    """Tag translations payload for German locale."""

    name = serializers.CharField(max_length=100, validators=[validate_serializer_name])


class TagTranslationsSerializer(serializers.Serializer):
    """Group translations under language keys."""

    ru = TagTranslationsRuSerializer()
    en = TagTranslationsEnSerializer()
    de = TagTranslationsDeSerializer()


@extend_schema_field(
    {
        'type': 'object',
        'required': ['ru', 'en', 'de'],
        'properties': {
            'ru': {'$ref': '#/components/schemas/TagTranslationsRu'},
            'en': {'$ref': '#/components/schemas/TagTranslationsEn'},
            'de': {'$ref': '#/components/schemas/TagTranslationsDe'},
        },
    },
)
class TagTranslatedFieldsField(TranslatedFieldsField):
    """Custom field to provide explicit openapi schema for translations."""


class TagSerializer(TranslatableModelSerializer):
    """Serializer for Tag model with explicit translations payload."""

    slug = serializers.SlugField(read_only=True)

    translations = TagTranslatedFieldsField(shared_model=Tag)

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

    @staticmethod
    def _clone_request_data(data: Any) -> Any:
        """Return mutable payload clone without deep-copying uploaded file objects.

        Args:
            data (Any): Raw request payload.

        Returns:
            Any: A mutable copy suitable for serializer normalization.
        """
        if isinstance(data, QueryDict):
            mutable_data = QueryDict('', mutable=True)
            for key, values in data.lists():
                mutable_data.setlist(key, list(values))
            return mutable_data
        return data.copy() if hasattr(data, 'copy') else data

    @staticmethod
    def _get_raw_tags(data: Any) -> tuple[Any | None, Any | None]:
        """Extract raw tags values from request payload.

        Args:
            data (Any): Raw request payload.

        Returns:
            tuple[Any | None, Any | None]: Tuple contains raw tags value and raw tags list from getlist(), if available.
        """
        raw_tags = data.get('tags') if hasattr(data, 'get') else None
        raw_tags_list = data.getlist('tags') if hasattr(data, 'getlist') else None
        return raw_tags, raw_tags_list

    @staticmethod
    def _normalize_raw_tag_values(raw_tags: Any | None, raw_tags_list: Any | None) -> list[Any] | None:
        """Normalize raw tags into a list-of-values or None.

        Args:
            raw_tags (Any | None): The raw 'tags' (a single value, a list, or None).
            raw_tags_list (Any | None): The optional raw 'tags' list extracted from the request using getlist().

        Returns:
            list[Any] | None: Normalized list of tag values ready for token extraction, or None if no tags.
        """
        if raw_tags_list is not None:
            return raw_tags_list
        if isinstance(raw_tags, list):
            return raw_tags
        if raw_tags is not None:
            return [raw_tags]
        return None

    @staticmethod
    def _extract_tag_tokens(raw_tag_values: list[Any]) -> list[Any]:
        """Split tag tokens by comma and drop empty values.

        Args:
            raw_tag_values (list[Any]): List of raw tag values extracted from the request.

        Returns:
            list[Any]: A flat list of individual tag tokens ready for coercion into tag ids.
        """
        tokens: list[Any] = []
        for raw_value in raw_tag_values:
            if isinstance(raw_value, str) and ',' in raw_value:
                tokens.extend(part.strip() for part in raw_value.split(',') if part.strip())
            elif raw_value not in {None, ''}:
                tokens.append(raw_value)
        return tokens

    @staticmethod
    def _coerce_tag_ids(tag_tokens: list[Any]) -> list[int]:
        """Convert any tag token into integer tag id or raise validation error.

        Args:
            tag_tokens (list[Any]): List of raw tag tokens extracted from the request.

        Raises:
            serializers.ValidationError: If any token cannot be coerced into an integer tag id.

        Returns:
            list[int]: List of coerced integer tag ids ready for serializer processing.
        """
        coerced_tag_ids: list[int] = []
        for token in tag_tokens:
            try:
                coerced_tag_ids.append(int(token))
            except (TypeError, ValueError) as exc:
                raise serializers.ValidationError({'tags': [f'Invalid tag id: {token!r}.']}) from exc
        return coerced_tag_ids

    @staticmethod
    def _apply_normalized_tags(data: Any, coerced_tag_ids: list[int]) -> Any:
        """Put normalized tags list back into mutable payload copy.

        Args:
            data (Any): Original request payload.
            coerced_tag_ids (list[int]): Normalized list of tag ids to set in the payload.

        Returns:
            Any: A mutable copy of the original payload with normalized tags list.
        """
        mutable_data = BookWriteSerializer._clone_request_data(data)
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
        return mutable_data

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        """Log and normalize raw tags payload before DRF field conversion.

        Raises:
            serializers.ValidationError: If tags cannot be coerced into a list of integers.

        Returns:
            dict[str, Any]: Normalized and validated data ready for model instance creation/update.
        """
        raw_tags, raw_tags_list = self._get_raw_tags(data)
        logger.warning('[BookWriteSerializer.to_internal_value] raw tags = %r', raw_tags)
        logger.warning('[BookWriteSerializer.to_internal_value] raw tags getlist = %r', raw_tags_list)

        normalized_data = data

        raw_tag_values = self._normalize_raw_tag_values(raw_tags, raw_tags_list)
        if raw_tag_values is not None:
            tag_tokens = self._extract_tag_tokens(raw_tag_values)
            coerced_tag_ids = self._coerce_tag_ids(tag_tokens)
            normalized_data = self._apply_normalized_tags(data, coerced_tag_ids)

        try:
            validated = super().to_internal_value(normalized_data)
            logger.warning('[BookWriteSerializer.to_internal_value] parsed tags = %r', validated.get('tags'))
            return cast('dict[str, Any]', validated)
        except serializers.ValidationError as exc:
            logger.warning('[BookWriteSerializer.to_internal_value] validation error detail = %r', exc.detail)
            raise

    def _get_effective_title_and_authors(self, attrs: dict[str, Any]) -> tuple[str | None, list[Author]]:
        """Return title and authors that should be used for duplicate checks.

        Args:
            attrs (dict[str, Any]): Incoming serializer attributes.

        Returns:
            tuple[str | None, list[Author]]: Effective title and author list for create/update validation.
        """
        effective_title = cast('str | None', attrs.get('title', getattr(self.instance, 'title', None)))
        effective_authors = attrs.get('authors')
        if effective_authors is None and self.instance is not None:
            effective_authors = list(self.instance.authors.all())
        return effective_title, list(effective_authors or [])

    def _validate_duplicate_book(self, title: str | None, authors: list[Author], book_type: str) -> None:
        """Reject save when a book with same title and author already exists.

        Args:
            title (str | None): Effective book title.
            authors (list[Author]): Effective list of authors.
            book_type (str): Effective book type.

        Raises:
            serializers.ValidationError: If duplicate title+author pair is found.
        """
        if not title or not authors:
            return

        duplicate_books = Book.objects.filter(
            title__iexact=title,
            authors__in=authors,
            book_type=book_type,
        ).distinct()
        if self.instance:
            duplicate_books = duplicate_books.exclude(pk=self.instance.pk)
        if duplicate_books.exists():
            raise serializers.ValidationError(
                {'title': 'A book with this title and author already exists.'},
            )

    def _validate_required_counts(self, attrs: dict[str, Any], book_type: str) -> None:
        """Validate required pages_total/chapters_total based on book type.

        Args:
            attrs (dict[str, Any]): Incoming serializer attributes.
            book_type (str): Effective type of book.

        Raises:
            serializers.ValidationError: If required counter field is missing for selected book type.
        """
        if not self.partial:
            if book_type == BookType.BOOK and not attrs.get('pages_total'):
                raise serializers.ValidationError(
                    {'pages_total': 'pages_total is required for book type "book".'},
                )
            if book_type == BookType.COMIC and not attrs.get('chapters_total'):
                raise serializers.ValidationError(
                    {'chapters_total': 'chapters_total is required for book type "comic".'},
                )
            return

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
        book_type = attrs.get('book_type', getattr(self.instance, 'book_type', BookType.BOOK))
        if authors is not None and len(authors) > AUTHOR_MAX_COUNT:
            raise serializers.ValidationError(
                {'authors': f'A book can have at most {AUTHOR_MAX_COUNT} authors.'},
            )

        effective_title, effective_authors = self._get_effective_title_and_authors(attrs)
        self._validate_duplicate_book(effective_title, effective_authors, book_type)

        if len(tags) > TAG_MAX_COUNT:
            raise serializers.ValidationError(
                {'tags': f'A book can have at most {TAG_MAX_COUNT} tags.'},
            )
        self._validate_required_counts(attrs, book_type)

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
