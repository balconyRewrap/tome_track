"""Common shared views used across the project.

This module is intentionally small and only contains views that are reused
in multiple places (e.g. health checks, feature-agnostic endpoints).
"""

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK
from rest_framework.views import APIView


class HealthCheckSerializer(serializers.Serializer):
    """Serializer for health check endpoint response."""

    status = serializers.CharField()


@extend_schema(
    summary="Health check endpoint",
    description="Returns 200 OK if the application is running.",
    responses={200: HealthCheckSerializer},
    tags=["Health"],
)
class HealthCheckView(APIView):
    """Simple health check endpoint.

    This endpoint is intended to be used by load balancers / uptime monitors.
    It does not require authentication and should be extremely cheap.
    """

    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):  # noqa: ARG002
        return Response({"status": "ok"}, status=HTTP_200_OK)