"""
URL configuration for Expense_Tracker project.
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.static import serve as static_serve

urlpatterns = [
    path('admin/', admin.site.urls),
    # Served at the domain root (not /static/sw.js) so its default scope is
    # "/" and it can control the whole app, not just the static directory.
    path('sw.js', static_serve, {'document_root': settings.BASE_DIR / 'static', 'path': 'sw.js'}, name='service_worker'),
    path('accounts/', include('accounts.urls')),
    path('accounts/', include('allauth.urls')),  # Google OAuth endpoints
    path('dashboard/', include('dashboard.urls')),
    path('expenses/', include('expenses.urls')),

    # JSON API for the Flutter mobile app (JWT-auth, local-first sync).
    # All of its logic/routing lives in Mobile_application/, separate from
    # the web app's views above - both read/write the same models.
    path('api/v1/', include('Mobile_application.urls')),

    path('', include('core.urls')),
]
