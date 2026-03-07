from rest_framework.permissions import BasePermission


class IsOwnerOrAdmin(BasePermission):
    """Custom permission to only allow owners of an object or admins to access it."""

    def has_object_permission(self, request, view, obj):
        """Check if has permission.

        Returns:
            bool: True if the user is the owner of the object or has admin role, False otherwise.
        """
        return getattr(obj, 'user', None) == request.user or getattr(request.user, 'role', None) == 'admin'


class IsAdminRole(BasePermission):
    """Custom permission to only allow users with admin role to access."""

    def has_permission(self, request, view):
        return getattr(request.user, 'role', None) == 'admin'


class IsOwner(BasePermission):
    """Custom permission to only allow owners of an object to access it."""

    def has_object_permission(self, request, view, obj):
        return getattr(obj, 'user', None) == request.user
