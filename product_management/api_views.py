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
