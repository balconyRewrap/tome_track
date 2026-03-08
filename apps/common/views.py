"""Views for common, now used for testing views."""
from django.core.cache import cache
from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@extend_schema(tags=['Testing'])
class GetCacheView(GenericAPIView):  # noqa: D101
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):  # noqa: ANN201, ANN001, ANN002, ANN003, ARG002, PLR6301, D102
        client = cache.client.get_client()  # pyright: ignore[reportAttributeAccessIssue]
        print(list(client.keys('*')))
        return Response({"message": "Cache keys printed to console."})
