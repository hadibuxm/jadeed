from django.urls import path
from . import views

app_name = "jira"

urlpatterns = [
    path("connect/", views.connect, name="connect"),
    path("callback/", views.callback, name="callback"),
    path("issues/", views.issues, name="issues"),
    path("issues/<str:key>/edit/", views.edit_issue, name="issue_edit"),
]

