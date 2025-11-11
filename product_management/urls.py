from django.urls import path
from . import views

app_name = 'product_management'

urlpatterns = [
    # Main dashboard
    path('', views.index, name='index'),

    # Project management
    path('project/create/', views.create_project, name='create_project'),
    path('project/<int:project_id>/', views.project_detail, name='project_detail'),

    # GitHub integration
    path('github/repos/', views.get_repositories, name='get_repositories'),
    path('github/repo/create/', views.create_github_repo, name='create_github_repo'),

    # Workflow steps
    path('project/<int:project_id>/step/create/', views.create_workflow_step, name='create_workflow_step'),
    path('workflow/<int:step_id>/', views.workflow_chat, name='workflow_chat'),
    path('workflow/<int:step_id>/message/', views.send_message, name='send_message'),
    path('workflow/<int:step_id>/conversation/', views.get_conversation, name='get_conversation'),
    path('workflow/<int:step_id>/readme/', views.generate_readme, name='generate_readme'),
    path('workflow/<int:step_id>/complete/', views.complete_step, name='complete_step'),
]
