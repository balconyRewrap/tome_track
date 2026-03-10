"""Permissions for users."""
from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class IsOwnerOrAdmin(BasePermission):
    """Custom permission to only allow owners of an object or admins to access it."""

    def has_object_permission(  # pyright: ignore[reportIncompatibleMethodOverride] # noqa: PLR6301
        self,
        request: Request,
        view: APIView,  # noqa: ARG002
        obj: Any,
    ) -> bool:
        """Check if has permission.

        Returns:
            bool: True if the user is the owner of the object or has admin role, False otherwise.
        """
        return getattr(obj, 'user', None) == request.user or getattr(request.user, 'role', None) == 'admin'


class IsAdminRole(BasePermission):
    """Custom permission to only allow users with admin role to access."""

    def has_permission(self, request: Request, view: APIView) -> bool:  # pyright: ignore[reportIncompatibleMethodOverride] # noqa: PLR6301, ARG002
        """Check if is admin.

        Returns:
            bool: True if the user has admin role, False otherwise.
        """
        return getattr(request.user, 'role', None) == 'admin'


class IsOwner(BasePermission):
    """Custom permission to only allow owners of an object to access it."""

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:  # pyright: ignore[reportIncompatibleMethodOverride] # noqa: PLR6301, ARG002
        """Check if is owner.

        Returns:
            bool: True if user is owner of object, False otherwise.
        """
        return getattr(obj, 'user', None) == request.user
