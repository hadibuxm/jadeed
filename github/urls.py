from django.urls import path
from . import views

app_name = 'github'

urlpatterns = [
    path('', views.index, name='index'),
    path('connect/', views.connect, name='connect'),
    path('callback/', views.callback, name='callback'),
    path('disconnect/', views.disconnect, name='disconnect'),
    path('fetch-repositories/', views.fetch_repositories, name='fetch_repositories')
    
]
