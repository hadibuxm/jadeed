"""
Management command to create a demo organization with sample data
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils.text import slugify
from decimal import Decimal
from datetime import date

from organizations.models import (
    Organization, Department, Team, Role,
    OrganizationMember, TeamMember
)
from accounting.models import Account


class Command(BaseCommand):
    help = 'Creates a demo organization with departments, teams, and roles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--org-name',
            type=str,
            default='Demo Tech Company',
            help='Name of the organization to create'
        )
        parser.add_argument(
            '--admin-username',
            type=str,
            default='admin',
            help='Username of the user to make admin'
        )

    def handle(self, *args, **options):
        org_name = options['org_name']
        admin_username = options['admin_username']

        # Check if organization already exists
        if Organization.objects.filter(name=org_name).exists():
            self.stdout.write(self.style.WARNING(f'Organization "{org_name}" already exists'))
            return

        # Get or create admin user
        try:
            admin_user = User.objects.get(username=admin_username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User "{admin_username}" does not exist'))
            self.stdout.write('Please create the user first or specify an existing username with --admin-username')
            return

        self.stdout.write(self.style.SUCCESS(f'Creating organization: {org_name}'))

        # Create Organization
        org = Organization.objects.create(
            name=org_name,
            slug=slugify(org_name),
            description='Demo organization for testing the accounting system',
            email=f'info@{slugify(org_name)}.com',
            phone='+1-555-0100',
            address_line1='123 Tech Street',
            city='San Francisco',
            state='CA',
            postal_code='94105',
            country='USA',
            tax_id='12-3456789',
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Created organization: {org.name}'))

        # Create default roles
        roles = Role.create_default_roles(org)
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(roles)} default roles'))

        # Create Departments
        engineering = Department.objects.create(
            organization=org,
            name='Engineering',
            slug='engineering',
            description='Software development and technology',
            head=admin_user,
            budget_allocated=Decimal('500000.00')
        )

        product = Department.objects.create(
            organization=org,
            name='Product',
            slug='product',
            description='Product management and design',
            budget_allocated=Decimal('200000.00')
        )

        finance = Department.objects.create(
            organization=org,
            name='Finance',
            slug='finance',
            description='Financial operations and accounting',
            budget_allocated=Decimal('150000.00')
        )

        self.stdout.write(self.style.SUCCESS(f'✓ Created 3 departments'))

        # Create Teams
        backend_team = Team.objects.create(
            department=engineering,
            name='Backend Team',
            slug='backend-team',
            description='Backend API development',
            lead=admin_user,
            project_key='BACKEND',
            budget_allocated=Decimal('250000.00')
        )

        frontend_team = Team.objects.create(
            department=engineering,
            name='Frontend Team',
            slug='frontend-team',
            description='Frontend UI development',
            project_key='FRONTEND',
            budget_allocated=Decimal('250000.00')
        )

        product_team = Team.objects.create(
            department=product,
            name='Product Strategy Team',
            slug='product-strategy',
            description='Product planning and strategy',
            budget_allocated=Decimal('100000.00')
        )

        self.stdout.write(self.style.SUCCESS(f'✓ Created 3 teams'))

        # Create Organization Member for admin
        admin_role = Role.objects.get(organization=org, role_type=Role.ADMIN)
        admin_member = OrganizationMember.objects.create(
            user=admin_user,
            organization=org,
            department=engineering,
            role=admin_role,
            employee_id='EMP001',
            job_title='CTO',
            salary=Decimal('150000.00'),
            date_joined=date.today(),
            is_active=True
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Created admin member: {admin_user.username}'))

        # Add admin to backend team
        TeamMember.objects.create(
            member=admin_member,
            team=backend_team,
            is_lead=True,
            is_active=True
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Added admin to backend team'))

        # Create Chart of Accounts
        self.stdout.write('Creating chart of accounts...')

        # Assets
        assets = Account.objects.create(
            organization=org,
            code='1000',
            name='Assets',
            account_type=Account.ASSET,
            description='All asset accounts'
        )

        Account.objects.create(
            organization=org,
            code='1100',
            name='Cash and Cash Equivalents',
            account_type=Account.ASSET,
            parent_account=assets,
            balance=Decimal('100000.00')
        )

        Account.objects.create(
            organization=org,
            code='1200',
            name='Accounts Receivable',
            account_type=Account.ASSET,
            parent_account=assets,
            balance=Decimal('50000.00')
        )

        # Liabilities
        liabilities = Account.objects.create(
            organization=org,
            code='2000',
            name='Liabilities',
            account_type=Account.LIABILITY,
            description='All liability accounts'
        )

        Account.objects.create(
            organization=org,
            code='2100',
            name='Accounts Payable',
            account_type=Account.LIABILITY,
            parent_account=liabilities,
            balance=Decimal('25000.00')
        )

        # Equity
        equity = Account.objects.create(
            organization=org,
            code='3000',
            name='Equity',
            account_type=Account.EQUITY,
            description='All equity accounts'
        )

        Account.objects.create(
            organization=org,
            code='3100',
            name='Retained Earnings',
            account_type=Account.EQUITY,
            parent_account=equity,
            balance=Decimal('75000.00')
        )

        # Revenue
        revenue = Account.objects.create(
            organization=org,
            code='4000',
            name='Revenue',
            account_type=Account.REVENUE,
            description='All revenue accounts'
        )

        Account.objects.create(
            organization=org,
            code='4100',
            name='Service Revenue',
            account_type=Account.REVENUE,
            parent_account=revenue
        )

        # Expenses
        expenses = Account.objects.create(
            organization=org,
            code='5000',
            name='Expenses',
            account_type=Account.EXPENSE,
            description='All expense accounts'
        )

        Account.objects.create(
            organization=org,
            code='5100',
            name='Salaries and Wages',
            account_type=Account.EXPENSE,
            parent_account=expenses
        )

        Account.objects.create(
            organization=org,
            code='5200',
            name='Travel and Entertainment',
            account_type=Account.EXPENSE,
            parent_account=expenses
        )

        Account.objects.create(
            organization=org,
            code='5300',
            name='Office Supplies',
            account_type=Account.EXPENSE,
            parent_account=expenses
        )

        Account.objects.create(
            organization=org,
            code='5400',
            name='Software and Subscriptions',
            account_type=Account.EXPENSE,
            parent_account=expenses
        )

        self.stdout.write(self.style.SUCCESS(f'✓ Created chart of accounts'))

        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('Demo organization created successfully!'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f'\nOrganization: {org.name}')
        self.stdout.write(f'Admin User: {admin_user.username}')
        self.stdout.write(f'Departments: {Department.objects.filter(organization=org).count()}')
        self.stdout.write(f'Teams: {Team.objects.filter(department__organization=org).count()}')
        self.stdout.write(f'Roles: {Role.objects.filter(organization=org).count()}')
        self.stdout.write(f'Accounts: {Account.objects.filter(organization=org).count()}')
        self.stdout.write(self.style.SUCCESS('\nYou can now log in with the admin user and start using the accounting system!'))
