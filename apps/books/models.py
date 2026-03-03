from django.db import models

from apps.common.models import TimestampedModel


# TODO: add more fields like bio, date of birth, etc.
# now is only test class for TT-1.3.1
class Author(TimestampedModel):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class Book(TimestampedModel):
    title = models.CharField(max_length=255)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='books')

    def __str__(self):
        return self.title
