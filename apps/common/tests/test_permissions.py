from types import SimpleNamespace

import pytest
from django.core.cache import cache

from apps.common.permissions import IsAdminRole, IsOwner, IsOwnerOrAdmin


def make_request(role: str | None = 'user') -> SimpleNamespace:
    """Return a minimal fake request with a user having the given role."""
    user = SimpleNamespace(role=role)
    return SimpleNamespace(user=user)


def make_obj(owner: object) -> SimpleNamespace:
    """Return a minimal fake object owned by *owner*."""
    return SimpleNamespace(user=owner)


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


# ---------------------------------------------------------------------------
# IsAdminRole
# ---------------------------------------------------------------------------

class TestIsAdminRole:
    perm = IsAdminRole()

    def test_admin_role_allowed(self):
        assert self.perm.has_permission(make_request('admin'), view=None) is True  # type: ignore[arg-type]

    def test_regular_user_denied(self):
        assert self.perm.has_permission(make_request('user'), view=None) is False  # type: ignore[arg-type]

    def test_no_role_attribute_denied(self):
        request = SimpleNamespace(user=SimpleNamespace())  # user has no `role`
        assert self.perm.has_permission(request, view=None) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# IsOwner
# ---------------------------------------------------------------------------

class TestIsOwner:
    perm = IsOwner()

    def test_owner_allowed(self):
        request = make_request('user')
        obj = make_obj(request.user)
        assert self.perm.has_object_permission(request, view=None, obj=obj) is True  # type: ignore[arg-type]

    def test_non_owner_denied(self):
        owner = SimpleNamespace(role='user', id=1)
        other = SimpleNamespace(role='user', id=2)
        request = make_request('user')
        request.user = other
        obj = make_obj(owner)
        assert self.perm.has_object_permission(request, view=None, obj=obj) is False  # type: ignore[arg-type]

    def test_obj_without_user_attribute_denied(self):
        request = make_request('user')
        obj = SimpleNamespace()  # no `user` attribute
        assert self.perm.has_object_permission(request, view=None, obj=obj) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# IsOwnerOrAdmin
# ---------------------------------------------------------------------------

class TestIsOwnerOrAdmin:
    perm = IsOwnerOrAdmin()

    def test_owner_allowed(self):
        request = make_request('user')
        obj = make_obj(request.user)
        assert self.perm.has_object_permission(request, view=None, obj=obj) is True  # type: ignore[arg-type]

    def test_admin_non_owner_allowed(self):
        owner = SimpleNamespace(role='user')
        request = make_request('admin')
        obj = make_obj(owner)
        assert self.perm.has_object_permission(request, view=None, obj=obj) is True  # type: ignore[arg-type]

    def test_non_owner_non_admin_denied(self):
        owner = SimpleNamespace(role='user', id=1)
        request = make_request('user')
        request.user = SimpleNamespace(role='user', id=2)
        obj = make_obj(owner)
        assert self.perm.has_object_permission(request, view=None, obj=obj) is False  # type: ignore[arg-type]

    def test_obj_without_user_attribute_admin_allowed(self):
        request = make_request('admin')
        obj = SimpleNamespace()  # no `user` attribute — admin wins via role check
        assert self.perm.has_object_permission(request, view=None, obj=obj) is True  # type: ignore[arg-type]

    def test_obj_without_user_attribute_regular_user_denied(self):
        request = make_request('user')
        obj = SimpleNamespace()  # no `user` attribute
        assert self.perm.has_object_permission(request, view=None, obj=obj) is False  # type: ignore[arg-type]

