from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal


class Organization(models.Model):
    """
    Represents a company or business entity.
    Top-level organizational unit that can have subsidiaries.
    """
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    # Hierarchical structure for subsidiaries
    parent_organization = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subsidiaries'
    )

    # Contact and billing information
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)

    # Address
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)

    # Tax and legal
    tax_id = models.CharField(max_length=50, blank=True, help_text="Tax ID or EIN")
    registration_number = models.CharField(max_length=50, blank=True)

    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Organization'
        verbose_name_plural = 'Organizations'

    def __str__(self):
        return self.name

    def get_all_members(self):
        """Get all members across all departments"""
        return OrganizationMember.objects.filter(
            department__organization=self
        ).select_related('user', 'department')


class Department(models.Model):
    """
    Departments within an organization (e.g., Engineering, Sales, Finance)
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='departments'
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    description = models.TextField(blank=True)

    # Department hierarchy
    parent_department = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sub_departments'
    )

    # Department head
    head = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_departments'
    )

    # Budget allocation
    budget_allocated = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['organization', 'name']
        unique_together = ['organization', 'slug']
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'

    def __str__(self):
        return f"{self.organization.name} - {self.name}"


class Team(models.Model):
    """
    Teams within departments for project-based work (like Jira teams)
    """
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='teams'
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    description = models.TextField(blank=True)

    # Team lead
    lead = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='led_teams'
    )

    # Project association
    project_key = models.CharField(
        max_length=50,
        blank=True,
        help_text="Associated Jira project key"
    )

    # Budget for this team/project
    budget_allocated = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['department', 'name']
        unique_together = ['department', 'slug']
        verbose_name = 'Team'
        verbose_name_plural = 'Teams'

    def __str__(self):
        return f"{self.department.name} - {self.name}"


class Role(models.Model):
    """
    Defines roles within the organization with specific permissions
    """
    ADMIN = 'ADMIN'
    MANAGER = 'MANAGER'
    ACCOUNTANT = 'ACCOUNTANT'
    EMPLOYEE = 'EMPLOYEE'
    VIEWER = 'VIEWER'

    ROLE_CHOICES = [
        (ADMIN, 'Admin'),
        (MANAGER, 'Manager'),
        (ACCOUNTANT, 'Accountant'),
        (EMPLOYEE, 'Employee'),
        (VIEWER, 'Viewer'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='roles'
    )
    name = models.CharField(max_length=100)
    role_type = models.CharField(max_length=20, choices=ROLE_CHOICES)
    description = models.TextField(blank=True)

    # Permissions
    can_manage_users = models.BooleanField(default=False)
    can_manage_roles = models.BooleanField(default=False)
    can_view_all_financial = models.BooleanField(default=False)
    can_manage_financial = models.BooleanField(default=False)
    can_approve_expenses = models.BooleanField(default=False)
    can_manage_departments = models.BooleanField(default=False)
    can_manage_teams = models.BooleanField(default=False)
    can_view_reports = models.BooleanField(default=False)
    can_export_data = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['organization', 'role_type']
        unique_together = ['organization', 'role_type']
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'

    def __str__(self):
        return f"{self.organization.name} - {self.get_role_type_display()}"

    @classmethod
    def create_default_roles(cls, organization):
        """Create default roles for a new organization"""
        default_roles = [
            {
                'role_type': cls.ADMIN,
                'name': 'Administrator',
                'description': 'Full access to all features',
                'can_manage_users': True,
                'can_manage_roles': True,
                'can_view_all_financial': True,
                'can_manage_financial': True,
                'can_approve_expenses': True,
                'can_manage_departments': True,
                'can_manage_teams': True,
                'can_view_reports': True,
                'can_export_data': True,
            },
            {
                'role_type': cls.MANAGER,
                'name': 'Manager',
                'description': 'Manage team and approve expenses',
                'can_manage_users': False,
                'can_manage_roles': False,
                'can_view_all_financial': False,
                'can_manage_financial': False,
                'can_approve_expenses': True,
                'can_manage_departments': False,
                'can_manage_teams': True,
                'can_view_reports': True,
                'can_export_data': False,
            },
            {
                'role_type': cls.ACCOUNTANT,
                'name': 'Accountant',
                'description': 'Manage financial records and reports',
                'can_manage_users': False,
                'can_manage_roles': False,
                'can_view_all_financial': True,
                'can_manage_financial': True,
                'can_approve_expenses': True,
                'can_manage_departments': False,
                'can_manage_teams': False,
                'can_view_reports': True,
                'can_export_data': True,
            },
            {
                'role_type': cls.EMPLOYEE,
                'name': 'Employee',
                'description': 'Standard employee access',
                'can_manage_users': False,
                'can_manage_roles': False,
                'can_view_all_financial': False,
                'can_manage_financial': False,
                'can_approve_expenses': False,
                'can_manage_departments': False,
                'can_manage_teams': False,
                'can_view_reports': False,
                'can_export_data': False,
            },
            {
                'role_type': cls.VIEWER,
                'name': 'Viewer',
                'description': 'Read-only access',
                'can_manage_users': False,
                'can_manage_roles': False,
                'can_view_all_financial': False,
                'can_manage_financial': False,
                'can_approve_expenses': False,
                'can_manage_departments': False,
                'can_manage_teams': False,
                'can_view_reports': True,
                'can_export_data': False,
            },
        ]

        created_roles = []
        for role_data in default_roles:
            role, created = cls.objects.get_or_create(
                organization=organization,
                role_type=role_data['role_type'],
                defaults=role_data
            )
            created_roles.append(role)

        return created_roles


class OrganizationMember(models.Model):
    """
    Links users to organizations with roles and department assignments
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='organization_memberships'
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='members'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members'
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name='members'
    )

    # Employment details
    employee_id = models.CharField(max_length=50, blank=True)
    job_title = models.CharField(max_length=255, blank=True)

    # Compensation
    salary = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    # Dates
    date_joined = models.DateField(null=True, blank=True)
    date_left = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['organization', 'user']
        unique_together = ['user', 'organization']
        verbose_name = 'Organization Member'
        verbose_name_plural = 'Organization Members'

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.organization.name}"

    def has_permission(self, permission_name):
        """Check if member has a specific permission"""
        return getattr(self.role, permission_name, False)


class TeamMember(models.Model):
    """
    Links organization members to specific teams
    """
    member = models.ForeignKey(
        OrganizationMember,
        on_delete=models.CASCADE,
        related_name='team_memberships'
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='members'
    )

    # Role within the team
    is_lead = models.BooleanField(default=False)

    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['team', 'member']
        unique_together = ['member', 'team']
        verbose_name = 'Team Member'
        verbose_name_plural = 'Team Members'

    def __str__(self):
        return f"{self.member.user.username} - {self.team.name}"
