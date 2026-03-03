"""Custom exception handlers for the Tome Track application.

This module defines custom exception handlers for both Django and Django REST Framework (DRF).
"""
from django.http import HttpRequest, JsonResponse
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_404(request: HttpRequest, exception: Exception) -> JsonResponse:  # noqa: ARG001
    """Custom 404 error handler that returns a JSON response.

    If request path starts with "/api/", it returns a structured JSON response with error details.
    Otherwise, it returns a generic not found message.

    Returns:
        JsonResponse: A JSON response with error details and a 404 status code.
    """
    if request.path.startswith("/api/"):
        return JsonResponse({
            "error": True,
            "message": "Endpoint not found",
            "status_code": 404,
        }, status=404)

    return JsonResponse({"detail": "Not found"}, status=404)


def custom_500(request: HttpRequest) -> JsonResponse:  # noqa: ARG001
    """Custom 500 error handler that returns a JSON response.

    Returns:
        JsonResponse: A JSON response with error details and a 500 status code.
    """
    return JsonResponse({
        "error": True,
        "message": "Internal server error",
        "status_code": 500,
    }, status=500)


def custom_exception_handler(exc: Exception, context: dict) -> Response | None:
    """Custom exception handler that formats DRF exceptions into a consistent JSON structure.

    Args:
        exc: The exception that was raised.
        context: Additional context about the exception.

    Returns:
        Response: A DRF Response object with a structured error message, or None if the exception is not handled.
    """
    response = exception_handler(exc, context)
    if response is not None and response.data is not None:
        response.data = {
            "error": {
                "code": response.status_code,
                "message": response.data.get('detail', 'Error'),
                "details": response.data,
            },
        }
    return response
