"""Mixins for views."""


class ActionPermissionsMixin:
    """Mixin to select permissions based on the current action.

    Define ``permission_classes_by_action`` mapping on the view, for example:

        permission_classes_by_action = {
            'list': [AllowAny],
            'create': [IsAuthenticated],
        }

    ``get_permissions`` will look up ``self.action``; if no entry is found
    it falls back to the usual ``permission_classes`` attribute.
    """

    permission_classes_by_action: dict[str, list] = {}

    def get_permissions(self) -> list:  # type: ignore[override]
        """Return the list of permissions that this view requires.

        Returns:
            list: List of permission instances.
        """
        if hasattr(self, 'action') and self.action in self.permission_classes_by_action:  # pyright: ignore[reportAttributeAccessIssue]
            classes = self.permission_classes_by_action[self.action]  # pyright: ignore[reportAttributeAccessIssue]
        else:
            classes = getattr(self, 'permission_classes', [])
        return [cls() for cls in classes]
