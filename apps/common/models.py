"""Common models for the Tome Track application."""
from django.db import models


class TimestampedModel(models.Model):
    """Abstract base model that provides timestamp tracking for Django models.

    This model automatically records the creation and last modification times
    for any model that inherits from it.

    Attributes:
        created_at (DateTimeField): Timestamp of when the instance was created. Automatically set on instance creation and cannot be modified.
        updated_at (DateTimeField): Timestamp of when the instance was last updated. Automatically updated whenever the instance is saved.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:  # noqa: D106
        abstract = True
