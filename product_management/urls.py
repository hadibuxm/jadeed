from django.urls import path

from . import views
from .api_views import (
    CreateFeatureAPIView,
    CreatePortfolioAPIView,
    CreateProductAPIView,
    CreateVisionAPIView,
    ListPortfoliosAPIView,
)

app_name = 'product_management'

urlpatterns = [
    # Main dashboard
    path('', views.index, name='index'),
    path('hierarchy/', views.hierarchy_view, name='hierarchy'),
    path('track-recent/', views.track_recent_item, name='track_recent_item'),
    path('update-status/', views.update_status, name='update_status'),
    path('create-vision/', CreateVisionAPIView.as_view(), name='create_vision'),
    path('create-portfolio/', CreatePortfolioAPIView.as_view(), name='create_portfolio'),
    path('portfolios/', ListPortfoliosAPIView.as_view(), name='list_portfolios'),
    path('create-product/', CreateProductAPIView.as_view(), name='create_product'),
    path('create-feature/', CreateFeatureAPIView.as_view(), name='create_feature'),

    # Project management
    path('project/create/', views.create_project, name='create_project'),
    path('project/<int:project_id>/', views.project_detail, name='project_detail'),
    path('project/<int:project_id>/delete/', views.delete_project, name='delete_project'),

    # GitHub integration
    path('github/repos/', views.get_repositories, name='get_repositories'),
    path('github/repo/create/', views.create_github_repo, name='create_github_repo'),

    # Workflow steps
    path('workflow/create/', views.create_workflow_step, name='create_workflow_step_standalone'),
    path('project/<int:project_id>/step/create/', views.create_workflow_step, name='create_workflow_step'),
    path('workflow/<int:step_id>/', views.workflow_chat, name='workflow_chat'),
    path('workflow/<int:step_id>/ensure-readme/', views.ensure_readme_synced, name='ensure_readme_synced'),
    path('workflow/<int:step_id>/update/', views.update_workflow_step, name='update_workflow_step'),
    path('workflow/<int:step_id>/message/', views.send_message, name='send_message'),
    path('workflow/<int:step_id>/comments/', views.workflow_comments, name='workflow_comments'),
    path('workflow/<int:step_id>/actions/', views.workflow_actions, name='workflow_actions'),
    path('workflow/<int:step_id>/actions/log/', views.create_workflow_action, name='create_workflow_action'),
    path('workflow/<int:step_id>/documents/', views.workflow_documents, name='workflow_documents'),
    path('workflow/<int:step_id>/conversation/', views.get_conversation, name='get_conversation'),
    path('workflow/<int:step_id>/readme/', views.generate_readme, name='generate_readme'),
    path('workflow/<int:step_id>/complete/', views.complete_step, name='complete_step'),
    path('workflow/<int:step_id>/delete/', views.delete_workflow_step, name='delete_workflow_step'),

    # Product steps
    path('product/<int:step_id>/steps/', views.product_steps, name='product_steps'),
    path('product/<int:step_id>/step/create/', views.create_product_step, name='create_product_step'),
    path('product-step/<int:product_step_id>/', views.product_step_chat, name='product_step_chat'),
    path('product-step/<int:product_step_id>/message/', views.send_product_step_message, name='send_product_step_message'),
    path('product-step/<int:product_step_id>/conversation/', views.get_product_step_conversation, name='get_product_step_conversation'),
    path('product-step/<int:product_step_id>/document/', views.generate_product_step_document, name='generate_product_step_document'),
    path('product-step/<int:product_step_id>/complete/', views.complete_product_step, name='complete_product_step'),
    path('product-step/<int:product_step_id>/delete/', views.delete_product_step, name='delete_product_step'),

    # Feature steps
    path('feature/<int:step_id>/steps/', views.feature_steps, name='feature_steps'),
    path('feature/<int:step_id>/step/create/', views.create_feature_step, name='create_feature_step'),
    path('feature-step/<int:feature_step_id>/', views.feature_step_chat, name='feature_step_chat'),
    path('feature-step/<int:feature_step_id>/message/', views.send_feature_step_message, name='send_feature_step_message'),
    path('feature-step/<int:feature_step_id>/conversation/', views.get_feature_step_conversation, name='get_feature_step_conversation'),
    path('feature-step/<int:feature_step_id>/document/', views.generate_feature_step_document, name='generate_feature_step_document'),
    path('feature-step/<int:feature_step_id>/complete/', views.complete_feature_step, name='complete_feature_step'),
    path('feature-step/<int:feature_step_id>/delete/', views.delete_feature_step, name='delete_feature_step'),
]
