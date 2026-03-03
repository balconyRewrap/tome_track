from rest_framework.views import exception_handler
from django.http import JsonResponse


def custom_404(request, exception):
    if request.path.startswith("/api/"):
        return JsonResponse({
            "error": True,
            "message": "Endpoint not found",
            "status_code": 404,
        }, status=404)

    return JsonResponse({"detail": "Not found"}, status=404)


def custom_500(request):
    return JsonResponse({
        "error": True,
        "message": "Internal server error",
        "status_code": 500,
    }, status=500)


def custom_exception_handler(exc, context):
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
