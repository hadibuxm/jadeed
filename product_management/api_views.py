import logging
from django.db import transaction
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils import timezone

from organizations.permissions import get_user_organization_member
from github.models import GitHubRepository

from .models import Vision, WorkflowStep, Portfolio, Product, Feature
from .ai_service import ProductDiscoveryAI
from .serializers import (
    VisionCreateSerializer,
    PortfolioCreateSerializer,
    ProductCreateSerializer,
    FeatureCreateSerializer,
)


logger = logging.getLogger(__name__)


def _can_access_workflow_step(step: WorkflowStep, user) -> bool:
    """Check if the requesting user owns the workflow step."""
    if step.project:
        return step.project.user_id == user.id
    if step.user_id:
        return step.user_id == user.id
    return False


def _serialize_document(document):
    """Serialize workflow document for API responses."""
    created = timezone.localtime(document.created_at)
    return {
        "id": document.id,
        "title": document.title,
        "document_type": document.document_type,
        "document_label": document.get_document_type_display(),
        "user": document.created_by.username if document.created_by else "System",
        "source": document.source,
        "content": document.content,
        "created_at": created.isoformat(),
    }


def _to_bool(value):
    """Coerce typical truthy inputs to boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return False


class CreateVisionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, *args, **kwargs):
        serializer = VisionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        member = get_user_organization_member(request.user)
        if not member:
            return Response(
                {
                    "success": False,
                    "errors": {
                        "organization": ["No active organization membership found."]
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        organization = member.organization
        if Vision.objects.filter(organization=organization).exists():
            return Response(
                {
                    "success": False,
                    "errors": {
                        "organization": ["This organization already has a vision."]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data
        with transaction.atomic():
            workflow_step = WorkflowStep.objects.create(
                project=None,
                user=request.user,
                step_type="vision",
                title=data["name"],
                description=data.get("description", ""),
                parent_step=None,
                status="backlog",
            )
            vision = Vision.objects.create(
                workflow_step=workflow_step,
                organization=organization,
            )

        return Response(
            {
                "success": True,
                "message": "Vision created successfully.",
                "data": {
                    "vision_id": vision.id,
                    "workflow_step_id": workflow_step.id,
                    "organization_id": organization.id,
                    "name": workflow_step.title,
                    "description": workflow_step.description,
                    "reference_id": workflow_step.reference_id,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class CreatePortfolioAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, *args, **kwargs):
        serializer = PortfolioCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        member = get_user_organization_member(request.user)
        if not member:
            return Response(
                {
                    "success": False,
                    "errors": {
                        "organization": ["No active organization membership found."]
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            vision = member.organization.vision
        except Vision.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "errors": {
                        "vision": ["No vision exists for this organization. Create one first."]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data
        
        # Check for duplicate portfolio name under this vision
        duplicate_exists = WorkflowStep.objects.filter(
            parent_step=vision.workflow_step,
            step_type="portfolio",
            title__iexact=data["name"]
        ).exists()
        
        if duplicate_exists:
            return Response(
                {
                    "success": False,
                    "errors": {
                        "name": ["A portfolio with this name already exists in this vision."]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        with transaction.atomic():
            workflow_step = WorkflowStep.objects.create(
                project=None,
                user=request.user,
                step_type="portfolio",
                title=data["name"],
                description=data.get("description", ""),
                parent_step=vision.workflow_step,
                status="backlog",
            )
            portfolio = Portfolio.objects.create(workflow_step=workflow_step)

        return Response(
            {
                "success": True,
                "message": "Portfolio created successfully.",
                "data": {
                    "portfolio_id": portfolio.id,
                    "workflow_step_id": workflow_step.id,
                    "organization_id": member.organization.id,
                    "vision_id": vision.id,
                    "name": workflow_step.title,
                    "description": workflow_step.description,
                    "reference_id": workflow_step.reference_id,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class ListPortfoliosAPIView(APIView):
    """List all portfolios for the authenticated user's organization."""
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, *args, **kwargs):
        member = get_user_organization_member(request.user)
        if not member:
            return Response(
                {
                    "success": False,
                    "errors": {
                        "organization": ["No active organization membership found."]
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            vision = member.organization.vision
        except Vision.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "errors": {
                        "vision": ["No vision exists for this organization. Create one first."]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get all portfolios that belong to this organization's vision
        portfolios = Portfolio.objects.select_related('workflow_step').filter(
            workflow_step__parent_step=vision.workflow_step
        ).order_by('workflow_step__created_at')

        portfolio_data = []
        for portfolio in portfolios:
            portfolio_data.append({
                "portfolio_id": portfolio.id,
                "workflow_step_id": portfolio.workflow_step.id,
                "name": portfolio.workflow_step.title,
                "description": portfolio.workflow_step.description,
                "reference_id": portfolio.workflow_step.reference_id,
                "status": portfolio.workflow_step.status,
                "created_at": portfolio.workflow_step.created_at.isoformat(),
            })

        return Response(
            {
                "success": True,
                "data": portfolio_data,
            },
            status=status.HTTP_200_OK,
        )


class ListVisionsAPIView(APIView):
    """List vision for the authenticated user's organization."""
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, *args, **kwargs):
        member = get_user_organization_member(request.user)
        if not member:
            return Response(
                {
                    "success": False,
                    "errors": {
                        "organization": ["No active organization membership found."]
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            vision = member.organization.vision
            vision_data = {
                "vision_id": vision.id,
                "workflow_step_id": vision.workflow_step.id,
                "name": vision.workflow_step.title,
                "description": vision.workflow_step.description,
                "reference_id": vision.workflow_step.reference_id,
                "status": vision.workflow_step.status,
                "created_at": vision.workflow_step.created_at.isoformat(),
            }
            
            return Response(
                {
                    "success": True,
                    "data": vision_data,
                },
                status=status.HTTP_200_OK,
            )
        except Vision.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "errors": {
                        "vision": ["No vision exists for this organization. Create one first."]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class ListProductsAPIView(APIView):
    """List all products for the authenticated user's organization."""
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, *args, **kwargs):
        member = get_user_organization_member(request.user)
        if not member:
            return Response(
                {
                    "success": False,
                    "errors": {
                        "organization": ["No active organization membership found."]
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            vision = member.organization.vision
        except Vision.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "errors": {
                        "vision": ["No vision exists for this organization. Create one first."]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get all portfolios that belong to this organization's vision
        portfolios = Portfolio.objects.select_related('workflow_step').filter(
            workflow_step__parent_step=vision.workflow_step
        )

        # Get all products that belong to these portfolios
        products = Product.objects.select_related('workflow_step').filter(
            workflow_step__parent_step__in=[p.workflow_step for p in portfolios]
        ).prefetch_related('repositories').order_by('workflow_step__created_at')

        product_data = []
        for product in products:
            # Get the portfolio this product belongs to
            portfolio = portfolios.filter(workflow_step=product.workflow_step.parent_step).first()
            
            product_data.append({
                "product_id": product.id,
                "workflow_step_id": product.workflow_step.id,
                "portfolio_id": portfolio.id if portfolio else None,
                "name": product.workflow_step.title,
                "description": product.workflow_step.description,
                "reference_id": product.workflow_step.reference_id,
                "status": product.workflow_step.status,
                "created_at": product.workflow_step.created_at.isoformat(),
                "github_repositories": [
                    {
                        "id": repo.id,
                        "name": repo.name,
                        "full_name": repo.full_name
                    }
                    for repo in product.repositories.all()
                ],
            })

        return Response(
            {
                "success": True,
                "data": product_data,
            },
            status=status.HTTP_200_OK,
        )


class CreateProductAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, *args, **kwargs):
        serializer = ProductCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        member = get_user_organization_member(request.user)
        if not member:
            return Response(
                {
                    "success": False,
                    "errors": {
                        "organization": ["No active organization membership found."]
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            org_vision = member.organization.vision
        except Vision.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "errors": {
                        "vision": ["No vision exists for this organization. Create one first."]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data
        try:
            portfolio = Portfolio.objects.select_related("workflow_step").get(
                id=data["portfolio_id"]
            )
        except Portfolio.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "errors": {"portfolio_id": ["Portfolio not found."]},
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        root_vision_step = portfolio.workflow_step.get_root_vision()
        if not root_vision_step or root_vision_step.id != org_vision.workflow_step_id:
            return Response(
                {
                    "success": False,
                    "errors": {
                        "portfolio_id": [
                            "Portfolio is not linked to your organization's vision."
                        ]
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check for duplicate product name under this portfolio
        duplicate_exists = WorkflowStep.objects.filter(
            parent_step=portfolio.workflow_step,
            step_type="product",
            title__iexact=data["name"]
        ).exists()
        
        if duplicate_exists:
            return Response(
                {
                    "success": False,
                    "errors": {
                        "name": ["A product with this name already exists in this portfolio."]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        repo_ids = data.get("github_repository_ids") or []
        
        # Validate that at least one repository is provided
        if not repo_ids or len(repo_ids) == 0:
            return Response(
                {
                    "success": False,
                    "errors": {
                        "github_repository_ids": [
                            "At least one GitHub repository is required for product creation."
                        ]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        repositories = list(
            GitHubRepository.objects.filter(
                id__in=repo_ids,
                connection__user=request.user,
            )
        )
        if len(repositories) != len(repo_ids):
            return Response(
                {
                    "success": False,
                    "errors": {
                        "github_repository_ids": [
                            "One or more repositories were not found for this user."
                        ]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            workflow_step = WorkflowStep.objects.create(
                project=None,
                user=request.user,
                step_type="product",
                title=data["name"],
                description=data.get("description", ""),
                parent_step=portfolio.workflow_step,
                status="backlog",
            )
            product = Product.objects.create(workflow_step=workflow_step)
            if repositories:
                product.repositories.set(repositories)

        return Response(
            {
                "success": True,
                "message": "Product created successfully.",
                "data": {
                    "product_id": product.id,
                    "workflow_step_id": workflow_step.id,
                    "portfolio_id": portfolio.id,
                    "vision_id": org_vision.id,
                    "name": workflow_step.title,
                    "description": workflow_step.description,
                    "reference_id": workflow_step.reference_id,
                    "github_repositories": [
                        {"id": repo.id, "name": repo.name, "full_name": repo.full_name}
                        for repo in repositories
                    ],
                },
            },
            status=status.HTTP_201_CREATED,
        )


class ListFeaturesAPIView(APIView):
    """List all features for the authenticated user's organization."""
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, *args, **kwargs):
        member = get_user_organization_member(request.user)
        if not member:
            return Response(
                {
                    "success": False,
                    "errors": {
                        "organization": ["No active organization membership found."]
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            vision = member.organization.vision
        except Vision.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "errors": {
                        "vision": ["No vision exists for this organization. Create one first."]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get all portfolios that belong to this organization's vision
        portfolios = Portfolio.objects.select_related('workflow_step').filter(
            workflow_step__parent_step=vision.workflow_step
        )

        # Get all products that belong to these portfolios
        products = Product.objects.select_related('workflow_step').filter(
            workflow_step__parent_step__in=[p.workflow_step for p in portfolios]
        )

        # Get all features that belong to these products
        features = Feature.objects.select_related('workflow_step', 'repository').filter(
            workflow_step__parent_step__in=[p.workflow_step for p in products]
        ).order_by('workflow_step__created_at')

        feature_data = []
        for feature in features:
            # Get the product this feature belongs to
            product = products.filter(workflow_step=feature.workflow_step.parent_step).first()
            
            feature_data.append({
                "feature_id": feature.id,
                "workflow_step_id": feature.workflow_step.id,
                "product_id": product.id if product else None,
                "name": feature.workflow_step.title,
                "description": feature.workflow_step.description,
                "reference_id": feature.workflow_step.reference_id,
                "status": feature.workflow_step.status,
                "priority": feature.priority,
                "created_at": feature.workflow_step.created_at.isoformat(),
                "github_repository": (
                    {
                        "id": feature.repository.id,
                        "name": feature.repository.name,
                        "full_name": feature.repository.full_name
                    }
                    if feature.repository
                    else None
                ),
            })

        return Response(
            {
                "success": True,
                "data": feature_data,
            },
            status=status.HTTP_200_OK,
        )


class CreateFeatureAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, *args, **kwargs):
        serializer = FeatureCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        member = get_user_organization_member(request.user)
        if not member:
            return Response(
                {
                    "success": False,
                    "errors": {
                        "organization": ["No active organization membership found."]
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            org_vision = member.organization.vision
        except Vision.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "errors": {
                        "vision": ["No vision exists for this organization. Create one first."]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data
        try:
            product = Product.objects.select_related("workflow_step").get(
                id=data["product_id"]
            )
        except Product.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "errors": {"product_id": ["Product not found."]},
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        root_vision_step = product.workflow_step.get_root_vision()
        if not root_vision_step or root_vision_step.id != org_vision.workflow_step_id:
            return Response(
                {
                    "success": False,
                    "errors": {
                        "product_id": [
                            "Product is not linked to your organization's vision."
                        ]
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check for duplicate feature name under this product
        duplicate_exists = WorkflowStep.objects.filter(
            parent_step=product.workflow_step,
            step_type="feature",
            title__iexact=data["name"]
        ).exists()
        
        if duplicate_exists:
            return Response(
                {
                    "success": False,
                    "errors": {
                        "name": ["A feature with this name already exists in this product."]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        repo = None
        repo_id = data.get("github_repository_id")
        if repo_id is not None:
            try:
                repo = GitHubRepository.objects.get(
                    id=repo_id, connection__user=request.user
                )
            except GitHubRepository.DoesNotExist:
                return Response(
                    {
                        "success": False,
                        "errors": {
                            "github_repository_id": ["Repository not found for this user."]
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        with transaction.atomic():
            workflow_step = WorkflowStep.objects.create(
                project=None,
                user=request.user,
                step_type="feature",
                title=data["name"],
                description=data.get("description", ""),
                parent_step=product.workflow_step,
                status="backlog",
            )
            feature = Feature.objects.create(
                workflow_step=workflow_step,
                repository=repo,
            )

        return Response(
            {
                "success": True,
                "message": "Feature created successfully.",
                "data": {
                    "feature_id": feature.id,
                    "workflow_step_id": workflow_step.id,
                    "product_id": product.id,
                    "vision_id": org_vision.id,
                    "name": workflow_step.title,
                    "description": workflow_step.description,
                    "reference_id": workflow_step.reference_id,
                    "github_repository": (
                        {"id": repo.id, "name": repo.name, "full_name": repo.full_name}
                        if repo
                        else None
                    ),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class WorkflowMessageAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, step_id, *args, **kwargs):
        workflow_step = get_object_or_404(WorkflowStep, id=step_id)

        if not _can_access_workflow_step(workflow_step, request.user):
            return Response(
                {"success": False, "error": "Workflow step not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        message = (request.data.get("message") or "").strip()
        use_streaming = request.data.get("stream", True)
        if isinstance(use_streaming, str):
            use_streaming = use_streaming.lower() != "false"

        if not message:
            return Response(
                {"success": False, "error": "Message cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ai_service = ProductDiscoveryAI(workflow_step)

        if use_streaming:
            response = StreamingHttpResponse(
                ai_service.send_message_stream(message),
                content_type="text/event-stream",
            )
            response["Cache-Control"] = "no-cache"
            response["X-Accel-Buffering"] = "no"
            return response

        result = ai_service.send_message(message)
        return Response(result, status=status.HTTP_200_OK)


class WorkflowConversationAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, step_id, *args, **kwargs):
        workflow_step = get_object_or_404(WorkflowStep, id=step_id)

        if not _can_access_workflow_step(workflow_step, request.user):
            return Response(
                {"success": False, "error": "Workflow step not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "success": True,
                "conversation": workflow_step.conversation_history,
                "readme_content": workflow_step.readme_content,
                "is_completed": workflow_step.is_completed,
            },
            status=status.HTTP_200_OK,
        )


class WorkflowGenerateReadmeAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, step_id, *args, **kwargs):
        workflow_step = get_object_or_404(WorkflowStep, id=step_id)

        if not _can_access_workflow_step(workflow_step, request.user):
            return Response(
                {"success": False, "error": "Workflow step not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            if workflow_step.status != "in_progress":
                workflow_step.status = "in_progress"
                workflow_step.save(update_fields=["status"])

            ai_service = ProductDiscoveryAI(workflow_step)
            result = ai_service.generate_readme()
            response_data = dict(result)
            document_entry = None

            if result.get("success"):
                readme_content = result.get("readme_content") or workflow_step.readme_content
                if readme_content:
                    document_entry = workflow_step.save_document_version(
                        title=f"README - {timezone.localtime(timezone.now()).strftime('%b %d, %Y %H:%M')}",
                        content=readme_content,
                        document_type="readme",
                        user=request.user,
                        source="ai",
                    )
                    workflow_step.log_action(
                        "readme_generated",
                        request.user,
                        description=document_entry.title,
                        metadata={"document_id": document_entry.id},
                    )
                    response_data["document"] = _serialize_document(document_entry)

                save_to_github = _to_bool(request.data.get("save_to_github")) or _to_bool(
                    request.query_params.get("save_to_github")
                )

                target_repository = None
                if workflow_step.step_type == "feature":
                    try:
                        target_repository = workflow_step.feature_details.repository
                    except Feature.DoesNotExist:
                        target_repository = None
                elif workflow_step.project:
                    target_repository = workflow_step.project.github_repository

                if save_to_github and target_repository:
                    try:
                        github_connection = request.user.github_connection
                        github_result = ai_service.save_readme_to_github(
                            github_connection, target_repository
                        )
                        if github_result.get("success"):
                            response_data["github_url"] = github_result.get("url")
                            response_data["github_file_path"] = github_result.get("file_path")
                            response_data["message"] = "README generated and saved to GitHub!"
                            workflow_step.log_action(
                                "document_saved",
                                request.user,
                                description=f"README pushed to GitHub ({github_result.get('file_path')})",
                                metadata={
                                    "document_id": document_entry.id if document_entry else None,
                                    "github_url": github_result.get("url"),
                                },
                            )
                        else:
                            response_data["github_error"] = github_result.get("error", "Unknown error")
                            response_data["message"] = "README generated but failed to save to GitHub"
                    except Exception as github_error:  # pragma: no cover - defensive
                        logger.error("Error saving README to GitHub", exc_info=True)
                        response_data["github_error"] = str(github_error)
                        response_data["message"] = "README generated but failed to save to GitHub"

            status_code = status.HTTP_200_OK if result.get("success") else status.HTTP_400_BAD_REQUEST
            return Response(response_data, status=status_code)

        except Exception as exc:  # pragma: no cover - defensive
            logger.error(f"Error generating README: {exc}", exc_info=True)
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
