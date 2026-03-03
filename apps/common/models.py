"""Common models for the Tome Track application."""
from django.db import models


class TimestampedModel(models.Model):
    """Abstract base class that provides self-updating 'created_at' and 'updated_at' fields."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:  # noqa: D106
        abstract = True
