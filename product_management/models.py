from django.db import models
from django.contrib.auth.models import User
from github.models import GitHubRepository
import json


class Project(models.Model):
    """Main project for product management."""
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pm_projects')
    github_repository = models.ForeignKey(
        GitHubRepository,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pm_projects'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Project"
        verbose_name_plural = "Projects"
        ordering = ['-created_at']


class WorkflowStep(models.Model):
    """Base model for workflow steps: Vision -> Initiative -> Portfolio -> Product -> Feature."""
    STEP_CHOICES = [
        ('vision', 'Vision'),
        ('initiative', 'Initiative'),
        ('portfolio', 'Portfolio'),
        ('product', 'Product'),
        ('feature', 'Feature'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='workflow_steps')
    step_type = models.CharField(max_length=20, choices=STEP_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Parent-child relationship for workflow hierarchy
    parent_step = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='child_steps'
    )

    # AI conversation history (stored as JSON)
    conversation_history = models.JSONField(default=list, blank=True)

    # README content generated from the conversation
    readme_content = models.TextField(blank=True)
    readme_generated_at = models.DateTimeField(null=True, blank=True)

    # Status
    is_completed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_step_type_display()} - {self.title}"

    def add_message(self, role, content):
        """Add a message to the conversation history."""
        if not isinstance(self.conversation_history, list):
            self.conversation_history = []

        self.conversation_history.append({
            'role': role,
            'content': content,
            'timestamp': None  # Will be serialized by Django
        })
        self.save()

    def get_conversation_context(self):
        """Get formatted conversation history for OpenAI API."""
        if not isinstance(self.conversation_history, list):
            return []

        return [
            {'role': msg['role'], 'content': msg['content']}
            for msg in self.conversation_history
        ]

    class Meta:
        verbose_name = "Workflow Step"
        verbose_name_plural = "Workflow Steps"
        ordering = ['step_type', '-created_at']
        indexes = [
            models.Index(fields=['project', 'step_type']),
            models.Index(fields=['parent_step']),
        ]


class Vision(models.Model):
    """Vision: The highest level strategic goal."""
    workflow_step = models.OneToOneField(
        WorkflowStep,
        on_delete=models.CASCADE,
        related_name='vision_details'
    )
    strategic_goals = models.TextField(blank=True)
    target_audience = models.TextField(blank=True)
    success_metrics = models.TextField(blank=True)

    def __str__(self):
        return f"Vision: {self.workflow_step.title}"

    class Meta:
        verbose_name = "Vision"
        verbose_name_plural = "Visions"


class Initiative(models.Model):
    """Initiative: Major strategic effort to achieve the vision."""
    workflow_step = models.OneToOneField(
        WorkflowStep,
        on_delete=models.CASCADE,
        related_name='initiative_details'
    )
    objectives = models.TextField(blank=True)
    key_results = models.TextField(blank=True)
    timeline = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"Initiative: {self.workflow_step.title}"

    class Meta:
        verbose_name = "Initiative"
        verbose_name_plural = "Initiatives"


class Portfolio(models.Model):
    """Portfolio: Collection of products working toward the initiative."""
    workflow_step = models.OneToOneField(
        WorkflowStep,
        on_delete=models.CASCADE,
        related_name='portfolio_details'
    )
    scope = models.TextField(blank=True)
    resource_allocation = models.TextField(blank=True)

    def __str__(self):
        return f"Portfolio: {self.workflow_step.title}"

    class Meta:
        verbose_name = "Portfolio"
        verbose_name_plural = "Portfolios"


class Product(models.Model):
    """Product: Specific product or service in the portfolio."""
    workflow_step = models.OneToOneField(
        WorkflowStep,
        on_delete=models.CASCADE,
        related_name='product_details'
    )
    value_proposition = models.TextField(blank=True)
    user_personas = models.TextField(blank=True)
    market_analysis = models.TextField(blank=True)

    def __str__(self):
        return f"Product: {self.workflow_step.title}"

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"


class Feature(models.Model):
    """Feature: Specific feature of a product."""
    workflow_step = models.OneToOneField(
        WorkflowStep,
        on_delete=models.CASCADE,
        related_name='feature_details'
    )
    user_story = models.TextField(blank=True)
    acceptance_criteria = models.TextField(blank=True)
    priority = models.CharField(
        max_length=20,
        choices=[
            ('critical', 'Critical'),
            ('high', 'High'),
            ('medium', 'Medium'),
            ('low', 'Low'),
        ],
        default='medium'
    )

    def __str__(self):
        return f"Feature: {self.workflow_step.title}"

    class Meta:
        verbose_name = "Feature"
        verbose_name_plural = "Features"


class ProductStep(models.Model):
    """Individual steps within a Product's development lifecycle."""

    STEP_TYPE_CHOICES = [
        # STRATEGIC / DISCOVERY LAYER
        ('market_context', 'Market Context'),
        ('discovery_research', 'Discovery Research'),
        ('problem_definition', 'Problem Definition'),
        ('hypothesis_business_case', 'Hypothesis & Business Case'),
        ('success_metrics', 'Success Metrics & Guardrails'),
        ('stakeholder_buyin', 'Stakeholder Buy-In'),

        # TACTICAL / BUILD LAYER
        ('ideation_design', 'Ideation & Solution Design'),
        ('prd_requirements', 'PRD / Requirements Definition'),
        ('design_prototypes', 'Design Prototypes + Validation'),
        ('development', 'Development'),
        ('qa_uat', 'QA, UAT, and Staging'),

        # RELEASE / IMPACT LAYER
        ('gtm_planning', 'Go-to-Market Planning'),
        ('release_execution', 'Release Execution'),
        ('post_launch', 'Post-Launch Validation'),
        ('retrospective', 'Retrospective & Learnings'),
    ]

    LAYER_CHOICES = [
        ('strategic', 'Strategic / Discovery Layer'),
        ('tactical', 'Tactical / Build Layer'),
        ('release', 'Release / Impact Layer'),
    ]

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='product_steps'
    )
    step_type = models.CharField(max_length=50, choices=STEP_TYPE_CHOICES)
    layer = models.CharField(max_length=20, choices=LAYER_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    # AI conversation history (stored as JSON)
    conversation_history = models.JSONField(default=list, blank=True)

    # Document content generated from the conversation
    document_content = models.TextField(blank=True)
    document_generated_at = models.DateTimeField(null=True, blank=True)

    # Status
    is_completed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_step_type_display()} - {self.title}"

    def add_message(self, role, content):
        """Add a message to the conversation history."""
        if not isinstance(self.conversation_history, list):
            self.conversation_history = []

        self.conversation_history.append({
            'role': role,
            'content': content,
            'timestamp': None
        })
        self.save()

    def get_conversation_context(self):
        """Get formatted conversation history for OpenAI API."""
        if not isinstance(self.conversation_history, list):
            return []

        return [
            {'role': msg['role'], 'content': msg['content']}
            for msg in self.conversation_history
        ]

    class Meta:
        verbose_name = "Product Step"
        verbose_name_plural = "Product Steps"
        ordering = ['product', 'order', 'created_at']
        indexes = [
            models.Index(fields=['product', 'step_type']),
            models.Index(fields=['product', 'order']),
        ]
