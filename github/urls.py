from django.urls import path
from . import views, api_views

app_name = 'github'

# API endpoints for Next.js frontend
api_urlpatterns = [
    path('api/', api_views.github_status, name='api_status'),
    path('api/connect/', api_views.github_connect, name='api_connect'),
    path('api/callback/', api_views.github_callback, name='api_callback'),
    path('api/sync/', api_views.github_sync, name='api_sync'),
    path('api/disconnect/', api_views.github_disconnect, name='api_disconnect'),
    path('api/request-code-change/', api_views.request_code_change, name='rest-request-code-change'),
    path('api/code-change-status/<int:request_id>/', api_views.code_change_status, name='rest-code-change-status'),
]

# Legacy template-based views (keep for backward compatibility)
template_urlpatterns = [
    path('', views.index, name='index'),
    path('connect/', views.connect, name='connect'),
    path('callback/', views.callback, name='callback'),
    path('disconnect/', views.disconnect, name='disconnect'),
    path('fetch-repositories/', views.fetch_repositories, name='fetch_repositories'),
    path('request-code-change/', views.request_code_change, name='request_code_change'),
    path('code-change-status/<int:request_id>/', views.get_code_change_status, name='get_code_change_status'),
]

urlpatterns = api_urlpatterns + template_urlpatterns
