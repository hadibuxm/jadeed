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

    STATUS_CHOICES = [
        ('backlog', 'Backlog'),
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='workflow_steps', null=True, blank=True)
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='workflow_steps', null=True, blank=True)
    step_type = models.CharField(max_length=20, choices=STEP_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Reference ID for Jira-like ticket numbering (e.g., ABC-0001)
    reference_id = models.CharField(max_length=20, unique=True, blank=True, null=True)

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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='backlog')
    is_completed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        ref_id = f"[{self.reference_id}] " if self.reference_id else ""
        return f"{ref_id}{self.get_step_type_display()} - {self.title}"

    def get_root_vision(self):
        """Traverse up the hierarchy to find the root Vision."""
        current = self
        while current.parent_step:
            current = current.parent_step

        # Return the Vision if found, else return self
        if current.step_type == 'vision':
            return current
        return None

    def generate_reference_prefix(self):
        """Generate a three-letter prefix from the vision title."""
        vision = self.get_root_vision()
        if not vision:
            # If no vision, use the item's own title
            title = self.title
        else:
            title = vision.title

        # Remove common words and extract meaningful parts
        words = title.upper().split()
        meaningful_words = [w for w in words if len(w) > 2 and w not in ['THE', 'AND', 'FOR', 'WITH']]

        if not meaningful_words:
            meaningful_words = words

        # Generate 3-letter code
        if len(meaningful_words) >= 3:
            # Take first letter of first 3 words
            prefix = ''.join([w[0] for w in meaningful_words[:3]])
        elif len(meaningful_words) == 2:
            # Take first letter of first word and first 2 letters of second
            prefix = meaningful_words[0][0] + meaningful_words[1][:2]
        elif len(meaningful_words) == 1:
            # Take first 3 letters of the word
            prefix = meaningful_words[0][:3]
        else:
            # Fallback to generic prefix
            prefix = 'WRK'

        return prefix[:3].upper()

    def generate_reference_id(self):
        """Generate a unique reference ID like ABC-0001."""
        if self.reference_id:
            return self.reference_id

        prefix = self.generate_reference_prefix()

        # Find the highest number used with this prefix
        existing_refs = WorkflowStep.objects.filter(
            reference_id__startswith=f"{prefix}-"
        ).values_list('reference_id', flat=True)

        numbers = []
        for ref in existing_refs:
            try:
                num = int(ref.split('-')[1])
                numbers.append(num)
            except (IndexError, ValueError):
                continue

        next_number = max(numbers) + 1 if numbers else 1

        return f"{prefix}-{next_number:04d}"

    def clean(self):
        """Validate hierarchy rules."""
        from django.core.exceptions import ValidationError

        # Define hierarchy order
        hierarchy_order = {
            'vision': 0,
            'initiative': 1,
            'portfolio': 2,
            'product': 3,
            'feature': 4
        }

        # Features MUST have a Product as parent
        if self.step_type == 'feature':
            if not self.parent_step:
                raise ValidationError('Features must be associated with a Product.')
            if self.parent_step.step_type != 'product':
                raise ValidationError('Features can only be created under a Product.')

        # Validate parent-child hierarchy order
        if self.parent_step:
            parent_level = hierarchy_order.get(self.parent_step.step_type, -1)
            child_level = hierarchy_order.get(self.step_type, -1)

            # Child must be exactly one level below parent
            if self.step_type == 'feature' and self.parent_step.step_type == 'product':
                # This is valid: Product -> Feature
                pass
            elif child_level != parent_level + 1:
                raise ValidationError(
                    f'Invalid hierarchy: {self.get_step_type_display()} cannot be a child of '
                    f'{self.parent_step.get_step_type_display()}. '
                    f'Valid hierarchy: Vision → Initiative → Portfolio → Product → Feature'
                )

        # Prevent circular references
        if self.parent_step:
            current = self.parent_step
            visited = set()
            while current:
                if current.id == self.id or current.id in visited:
                    raise ValidationError('Circular reference detected in hierarchy.')
                visited.add(current.id)
                current = current.parent_step

    def save(self, *args, **kwargs):
        """Override save to auto-generate reference_id and validate."""
        if not self.reference_id:
            self.reference_id = self.generate_reference_id()
        # Call clean to validate before saving
        self.clean()
        super().save(*args, **kwargs)

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

    def log_action(self, action_type, user=None, description='', metadata=None):
        """Persist an action entry tied to this workflow step."""
        if metadata is None:
            metadata = {}
        return WorkflowActionLog.objects.create(
            workflow_step=self,
            user=user,
            action_type=action_type,
            description=description,
            metadata=metadata,
        )

    def save_document_version(self, title, content, document_type='readme', user=None, source='ai'):
        """Store a generated document snapshot for future reference."""
        return WorkflowDocument.objects.create(
            workflow_step=self,
            document_type=document_type,
            title=title or f"{self.get_step_type_display()} Document",
            content=content,
            created_by=user,
            source=source,
        )

    class Meta:
        verbose_name = "Workflow Step"
        verbose_name_plural = "Workflow Steps"
        ordering = ['step_type', '-created_at']
        indexes = [
            models.Index(fields=['project', 'step_type']),
            models.Index(fields=['parent_step']),
        ]


class WorkflowComment(models.Model):
    """User comments attached to a workflow step."""
    workflow_step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='workflow_comments'
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Comment by {self.user} on {self.workflow_step}"

    class Meta:
        verbose_name = "Workflow Comment"
        verbose_name_plural = "Workflow Comments"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['workflow_step', '-created_at']),
        ]


class WorkflowActionLog(models.Model):
    """Audit log of notable user/system actions on a workflow step."""
    ACTION_CHOICES = [
        ('comment_added', 'Comment Added'),
        ('description_updated', 'Description Updated'),
        ('title_updated', 'Title Updated'),
        ('readme_generated', 'README Generated'),
        ('step_completed', 'Step Completed'),
        ('code_change_requested', 'Code Change Requested'),
        ('document_saved', 'Document Saved'),
    ]

    workflow_step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.CASCADE,
        related_name='action_logs'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workflow_action_logs'
    )
    action_type = models.CharField(max_length=50, choices=ACTION_CHOICES)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        user_display = self.user.username if self.user else 'System'
        return f"{user_display} - {self.get_action_type_display()}"

    class Meta:
        verbose_name = "Workflow Action Log"
        verbose_name_plural = "Workflow Action Logs"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['workflow_step', '-created_at']),
        ]


class WorkflowDocument(models.Model):
    """Stores generated documents (e.g., README revisions) for a workflow step."""
    DOCUMENT_TYPE_CHOICES = [
        ('readme', 'README'),
        ('summary', 'Summary'),
        ('spec', 'Specification'),
        ('other', 'Other'),
    ]

    workflow_step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    title = models.CharField(max_length=255)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES, default='readme')
    content = models.TextField()
    source = models.CharField(max_length=50, default='ai')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workflow_documents'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_document_type_display()} - {self.title}"

    class Meta:
        verbose_name = "Workflow Document"
        verbose_name_plural = "Workflow Documents"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['workflow_step', '-created_at']),
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


class FeatureStep(models.Model):
    """Individual steps within a Feature's development lifecycle."""

    STEP_TYPE_CHOICES = [
        # FEATURE-SPECIFIC STEPS
        ('requirements', 'Requirements & Specifications'),
        ('user_story', 'User Story Definition'),
        ('acceptance_criteria', 'Acceptance Criteria'),
        ('technical_design', 'Technical Design'),
        ('implementation', 'Implementation'),
        ('testing', 'Testing & QA'),
        ('code_review', 'Code Review'),
        ('documentation', 'Documentation'),
        ('deployment', 'Deployment'),
        ('validation', 'User Validation'),
    ]

    LAYER_CHOICES = [
        ('planning', 'Planning Layer'),
        ('development', 'Development Layer'),
        ('delivery', 'Delivery Layer'),
    ]

    feature = models.ForeignKey(
        Feature,
        on_delete=models.CASCADE,
        related_name='feature_steps'
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
        verbose_name = "Feature Step"
        verbose_name_plural = "Feature Steps"
        ordering = ['feature', 'order', 'created_at']
        indexes = [
            models.Index(fields=['feature', 'step_type']),
            models.Index(fields=['feature', 'order']),
        ]


class RecentItem(models.Model):
    """Track recently accessed items for quick navigation."""
    ITEM_TYPE_CHOICES = [
        ('product', 'Product'),
        ('feature', 'Feature'),
        ('project', 'Project'),
        ('workflow', 'Workflow Step'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recent_items')
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)
    item_id = models.PositiveIntegerField()
    item_title = models.CharField(max_length=255)
    item_url = models.CharField(max_length=500)
    accessed_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.item_type}: {self.item_title}"

    class Meta:
        verbose_name = "Recent Item"
        verbose_name_plural = "Recent Items"
        ordering = ['-accessed_at']
        indexes = [
            models.Index(fields=['user', '-accessed_at']),
        ]
        unique_together = ['user', 'item_type', 'item_id']
