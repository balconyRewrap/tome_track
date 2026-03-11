# Make Celery app available when Django starts so that @shared_task can use it.
from .celery import app as celery_app

__all__ = ('celery_app',)
