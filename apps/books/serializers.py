"""Serializers for Books application."""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.books.models import AUTHOR_MAX_COUNT, TAG_MAX_COUNT, Author, Book, BookType, Tag


# Annotating the *class* (not the instance) is the only reliable way to override
# drf-spectacular's built-in ImageField mapping, which ignores instance-level annotations.
@extend_schema_field({'type': 'string', 'format': 'binary'})
class CoverImageField(serializers.ImageField):
    """Class for schema override of cover image field in BookSerializer."""


class AuthorSerializer(serializers.ModelSerializer):
    """Serializer for Author model."""

    class Meta:  # noqa: D106
        model = Author
        fields = ['id', 'name']


class TagSerializer(serializers.ModelSerializer):
    """Serializer for Tag model."""

    class Meta:  # noqa: D106
        model = Tag
        fields = ['id', 'name', 'slug']


class BookSerializer(serializers.ModelSerializer):
    """Serializer for Book model with business validation."""

    cover = CoverImageField(use_url=True, required=False, allow_null=True)
    average_rating = serializers.FloatField(read_only=True)  # annotated
    ratings_count = serializers.IntegerField(read_only=True)  # annotated

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

    def to_internal_value(self, data):
        import json

        from django.http import QueryDict
        from rest_framework.relations import ManyRelatedField

        if isinstance(data, QueryDict):
            # multipart/form-data arrives as a QueryDict.
            # QueryDict.__setitem__ wraps every assigned value in an extra
            # list, so doing ``data['tags'] = []`` stores ``[[]]`` and
            # ManyRelatedField then receives ``[[]]`` via getlist() --
            # child sees a list instead of a PK -> 'received list.'
            # Also, a single author 'authors=1' gives get() = '1' (string)
            # while 'authors=1&authors=2' needs getlist() = ['1', '2'].
            # Converting to a plain dict up front avoids both problems.
            plain = data.dict()  # {key: last_value_string} for scalars
            for name, field in self.fields.items():
                if isinstance(field, ManyRelatedField):
                    plain[name] = data.getlist(name)
            data = plain

        # Normalise every M2M field.  Swagger produces garbage for empty
        # arrays ('', [''], [[]]) and sometimes sends an entire array as
        # a single JSON-encoded string (e.g. '["1","2"]').
        for name, field in self.fields.items():
            if not isinstance(field, ManyRelatedField):
                continue
            val = data.get(name)
            if val in ('', None):
                data = {**data, name: []}
            elif isinstance(val, list):
                # Try to unwrap a JSON-array sent as a single string item.
                if len(val) == 1 and isinstance(val[0], str):
                    try:
                        parsed = json.loads(val[0])
                        if isinstance(parsed, list):
                            val = parsed
                    except (json.JSONDecodeError, ValueError):
                        pass
                # Unwrap [[1, 2]] -> [1, 2]
                if len(val) == 1 and isinstance(val[0], (list, tuple)):
                    val = list(val[0])
                # Drop stray empty strings / empty lists
                data = {**data, name: [v for v in val if v not in ('', [], None)]}

        return super().to_internal_value(data)

    def validate(self, attrs: dict) -> dict:  # noqa: PLR6301
        """Validate cross-field business rules.

        Raises:
            serializers.ValidationError: If any business rule is violated.

        Returns:
            dict: The validated attributes.
        """
        authors = attrs.get('authors', [])
        tags = attrs.get('tags', [])
        book_type = attrs.get('book_type', BookType.BOOK)
        pages_total = attrs.get('pages_total')
        chapters_total = attrs.get('chapters_total')

        if len(authors) > AUTHOR_MAX_COUNT:
            raise serializers.ValidationError(
                {'authors': f'A book can have at most {AUTHOR_MAX_COUNT} authors.'},
            )

        if len(tags) > TAG_MAX_COUNT:
            raise serializers.ValidationError(
                {'tags': f'A book can have at most {TAG_MAX_COUNT} tags.'},
            )

        if book_type == BookType.BOOK and not pages_total:
            raise serializers.ValidationError(
                {'pages_total': 'pages_total is required for book type "book".'},
            )

        if book_type == BookType.COMIC and not chapters_total:
            raise serializers.ValidationError(
                {'chapters_total': 'chapters_total is required for book type "comic".'},
            )

        return attrs

# using bookwrite for PATCH break it if not changing authors, so i create special specializer for it.
class BookUpdateSerializer(BookSerializer):
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

    def to_internal_value(self, data):
        import json

        from django.http import QueryDict
        from rest_framework.relations import ManyRelatedField

        if isinstance(data, QueryDict):
            # multipart/form-data arrives as a QueryDict.
            # QueryDict.__setitem__ wraps every assigned value in an extra
            # list, so doing ``data['tags'] = []`` stores ``[[]]`` and
            # ManyRelatedField then receives ``[[]]`` via getlist() --
            # child sees a list instead of a PK -> 'received list.'
            # Also, a single author 'authors=1' gives get() = '1' (string)
            # while 'authors=1&authors=2' needs getlist() = ['1', '2'].
            # Converting to a plain dict up front avoids both problems.
            plain = data.dict()  # {key: last_value_string} for scalars
            for name, field in self.fields.items():
                if isinstance(field, ManyRelatedField):
                    plain[name] = data.getlist(name)
            data = plain

        # Normalise every M2M field.  Swagger produces garbage for empty
        # arrays ('', [''], [[]]) and sometimes sends an entire array as
        # a single JSON-encoded string (e.g. '["1","2"]').
        for name, field in self.fields.items():
            if not isinstance(field, ManyRelatedField):
                continue
            val = data.get(name)
            if val in ('', None):
                data = {**data, name: []}
            elif isinstance(val, list):
                # Try to unwrap a JSON-array sent as a single string item.
                if len(val) == 1 and isinstance(val[0], str):
                    try:
                        parsed = json.loads(val[0])
                        if isinstance(parsed, list):
                            val = parsed
                    except (json.JSONDecodeError, ValueError):
                        pass
                # Unwrap [[1, 2]] -> [1, 2]
                if len(val) == 1 and isinstance(val[0], (list, tuple)):
                    val = list(val[0])
                # Drop stray empty strings / empty lists
                data = {**data, name: [v for v in val if v not in ('', [], None)]}

        return super().to_internal_value(data)

    def validate(self, attrs: dict) -> dict:  # noqa: PLR6301
        """Validate cross-field business rules.

        Raises:
            serializers.ValidationError: If any business rule is violated.

        Returns:
            dict: The validated attributes.
        """
        _authors = attrs.get('authors')
        if _authors:
            authors = _authors
        tags = attrs.get('tags', [])
        book_type = attrs.get('book_type', BookType.BOOK)
        pages_total = attrs.get('pages_total')
        chapters_total = attrs.get('chapters_total')
        if _authors:
            if len(_authors) > AUTHOR_MAX_COUNT:
                raise serializers.ValidationError(
                    {'authors': f'A book can have at most {AUTHOR_MAX_COUNT} authors.'},
                )

        if len(tags) > TAG_MAX_COUNT:
            raise serializers.ValidationError(
                {'tags': f'A book can have at most {TAG_MAX_COUNT} tags.'},
            )

        if book_type == BookType.BOOK and not pages_total:
            raise serializers.ValidationError(
                {'pages_total': 'pages_total is required for book type "book".'},
            )

        if book_type == BookType.COMIC and not chapters_total:
            raise serializers.ValidationError(
                {'chapters_total': 'chapters_total is required for book type "comic".'},
            )

        return attrs