"""URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/

Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from apps.books.views import (
    AuthorViewSet,
    BookViewSet,
    TagViewSet,
)
from apps.users.views.admin import (
    AdminUserViewSet,
)
from apps.users.views.auth import (
    AuthCheckView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    LogoutView,
    RegisterView,
)
from apps.users.views.user import (
    ChangeEmailView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetView,
    UserMeView,
)

# admin
urlpatterns = [
    path('admin/', admin.site.urls),
]

# auth
urlpatterns += [
    path('api/v1/auth/register/', RegisterView.as_view(), name='register'),
    path('api/v1/auth/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/auth/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/auth/logout/', LogoutView.as_view(), name='logout'),
]

# user
urlpatterns += [
    path('api/v1/users/me/', UserMeView.as_view(), name='user_me'),
    path('api/v1/users/me/change-email/', ChangeEmailView.as_view(), name='change_email'),
    path('api/v1/users/password/reset/', PasswordResetView.as_view(), name='password_reset'),
    path('api/v1/users/password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('api/v1/users/password/change/', PasswordChangeView.as_view(), name='password_change'),
]

# admin
urlpatterns += [
    path('api/v1/admin/users/', AdminUserViewSet.as_view({'get': 'list'}), name='admin_users'),
    path(
        'api/v1/admin/users/<int:pk>/',
        AdminUserViewSet.as_view({'get': 'retrieve', 'patch': 'update'}),
        name='admin_user_detail',
    ),
]

# books
books = BookViewSet.as_view({
    'get':    'list',
    'post':   'create',
})

books_detail = BookViewSet.as_view({
    'get':    'retrieve',
    'put':    'update',
    'patch':  'partial_update',
    'delete': 'destroy',
})
urlpatterns += [
    path('api/v1/books/', books, name='books'),
    path('api/v1/books/<int:pk>/', books_detail, name='book_detail'),
]

authors = AuthorViewSet.as_view({'get': 'list', 'post': 'create'})
authors_detail = AuthorViewSet.as_view({'get': 'retrieve'})

urlpatterns += [
    path('api/v1/authors/', authors, name='authors'),
    path('api/v1/authors/<int:pk>/', authors_detail, name='author-detail'),
]

tags = TagViewSet.as_view({'get': 'list', 'post': 'create'})
tags_detail = TagViewSet.as_view({'get': 'retrieve'})

urlpatterns += [
    path('api/v1/tags/', tags, name='tags'),
    path('api/v1/tags/<int:pk>/', tags_detail, name='tag-detail'),
]


urlpatterns += [
    path('api/v1/auth/check/', AuthCheckView.as_view(), name='auth_check'),
]

# debug
if getattr(settings, 'DEBUG', False):
    urlpatterns += [
        path('api/v1/schema/', SpectacularAPIView.as_view(), name='schema'),
        path('api/v1/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
        path('api/v1/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    ]


handler404 = "apps.common.exceptions.custom_404"
handler500 = "apps.common.exceptions.custom_500"

# Serve uploaded media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
