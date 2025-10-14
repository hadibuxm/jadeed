from django.urls import path
from . import views

urlpatterns = [
    path('devinai/', views.devinai_integration, name='devinai_integration'),
    path('sessions/', views.list_sessions, name='list_sessions'),
    path('create-session/', views.create_session, name='create_session'),
    path('sessions/<str:session_id>/', views.retrieve_session, name='retrieve_session'),
]