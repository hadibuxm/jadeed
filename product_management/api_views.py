from django.db import transaction
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from organizations.permissions import get_user_organization_member
from github.models import GitHubRepository

from .models import Vision, WorkflowStep, Portfolio, Product, Feature
from .serializers import (
    VisionCreateSerializer,
    PortfolioCreateSerializer,
    ProductCreateSerializer,
    FeatureCreateSerializer,
)


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

        repo_ids = data.get("github_repository_ids") or []
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
