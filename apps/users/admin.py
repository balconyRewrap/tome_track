"""Admin of users app."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import QuerySet
from django.http.request import HttpRequest

from apps.users.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for the User model."""

    model = User
    list_display = ("id", "email", "username", "role", "is_active", "is_staff", "created_at")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "username")
    actions = ["activate_users", "deactivate_users"]
    ordering = ("email",)
    readonly_fields = ("created_at", "updated_at", "last_login")
    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Permissions", {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "password1", "password2", "role", "is_active", "is_staff"),
        }),
    )

    @admin.action(description="Activate Users")
    def activate_users(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        """Activate list of users.

        Args:
            request (HttpRequest): The request object.
            queryset (QuerySet[User]): The queryset of users to activate.
        """
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Users activated: {updated}")

    @admin.action(description="Deactivate Users")
    def deactivate_users(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        """Deactivate list of users.

        Args:
            request (HttpRequest): The request object.
            queryset (QuerySet[User]): The queryset of users to deactivate.
        """
        queryset = queryset.exclude(id=request.user.id)
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Users deactivated: {updated}")
