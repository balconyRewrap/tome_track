import pytest
import factory
from apps.books.models import Book, Author

class AuthorFactory(factory.django.DjangoModelFactory):
    class Meta:  # pyright: ignore
        model = Author

    name = factory.Sequence(lambda n: f"Author {n}")  # pyright: ignore

class BookFactory(factory.django.DjangoModelFactory):
    class Meta:  # pyright: ignore
        model = Book

    title = factory.Sequence(lambda n: f"Book {n}")  # pyright: ignore
    author = factory.SubFactory(AuthorFactory)  # pyright: ignore

@pytest.fixture
def book_factory():
    return BookFactory