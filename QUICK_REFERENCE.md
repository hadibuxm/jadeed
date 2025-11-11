# Quick Reference Guide

## Models Quick Reference

### Organizations App

```python
from organizations.models import (
    Organization, Department, Team, Role,
    OrganizationMember, TeamMember
)
```

#### Organization
```python
org = Organization.objects.create(
    name="Company Name",
    slug="company-name",
    email="info@company.com",
    # ... other fields
)
```

#### Department
```python
dept = Department.objects.create(
    organization=org,
    name="Engineering",
    slug="engineering",
    head=user,
    budget_allocated=Decimal('500000.00')
)
```

#### Team
```python
team = Team.objects.create(
    department=dept,
    name="Backend Team",
    slug="backend-team",
    lead=user,
    project_key="BACKEND",
    budget_allocated=Decimal('250000.00')
)
```

#### Role
```python
# Create default roles
roles = Role.create_default_roles(org)

# Or create custom role
role = Role.objects.create(
    organization=org,
    name="Custom Role",
    role_type=Role.EMPLOYEE,
    can_approve_expenses=True,
    # ... other permissions
)
```

#### OrganizationMember
```python
member = OrganizationMember.objects.create(
    user=user,
    organization=org,
    department=dept,
    role=role,
    employee_id="EMP001",
    job_title="Software Engineer",
    salary=Decimal('120000.00'),
    date_joined=date.today()
)

# Check permission
if member.has_permission('can_manage_users'):
    # User has permission
    pass
```

### Accounting App

```python
from accounting.models import (
    Account, Expense, Invoice, InvoiceLineItem,
    Payment, JournalEntry, JournalEntryLine, Budget
)
```

#### Account (Chart of Accounts)
```python
# Create parent account
assets = Account.objects.create(
    organization=org,
    code='1000',
    name='Assets',
    account_type=Account.ASSET
)

# Create sub-account
cash = Account.objects.create(
    organization=org,
    code='1100',
    name='Cash',
    account_type=Account.ASSET,
    parent_account=assets,
    balance=Decimal('50000.00')
)
```

#### Expense
```python
expense = Expense.objects.create(
    organization=org,
    member=org_member,
    department=dept,
    team=team,
    account=expense_account,
    title="Conference Travel",
    description="Annual tech conference",
    category=Expense.TRAVEL,
    amount=Decimal('1500.00'),
    expense_date=date.today(),
    status=Expense.PENDING
)

# Approve expense
expense.status = Expense.APPROVED
expense.approved_by = manager_user
expense.approved_date = timezone.now()
expense.save()
```

#### Invoice
```python
invoice = Invoice.objects.create(
    organization=org,
    invoice_number="INV-2024-001",
    invoice_type=Invoice.CUSTOMER,
    client_name="Client Name",
    client_email="client@example.com",
    subtotal=Decimal('10000.00'),
    tax_amount=Decimal('800.00'),
    total_amount=Decimal('10800.00'),
    issue_date=date.today(),
    due_date=date.today() + timedelta(days=30),
    status=Invoice.DRAFT
)

# Add line item
InvoiceLineItem.objects.create(
    invoice=invoice,
    description="Consulting Services",
    quantity=Decimal('10'),
    unit_price=Decimal('1000.00'),
    account=revenue_account
)
```

#### Payment
```python
payment = Payment.objects.create(
    organization=org,
    invoice=invoice,  # or expense=expense
    amount=Decimal('10800.00'),
    payment_method=Payment.BANK_TRANSFER,
    payment_date=date.today(),
    reference_number="TXN123456",
    processed_by=user
)
```

#### Journal Entry
```python
entry = JournalEntry.objects.create(
    organization=org,
    entry_number="JE-2024-001",
    entry_type=JournalEntry.STANDARD,
    entry_date=date.today(),
    description="Record expense",
    created_by=user
)

# Add debit line
JournalEntryLine.objects.create(
    journal_entry=entry,
    account=expense_account,
    debit_amount=Decimal('1500.00'),
    department=dept
)

# Add credit line
JournalEntryLine.objects.create(
    journal_entry=entry,
    account=cash_account,
    credit_amount=Decimal('1500.00'),
    department=dept
)

# Check if balanced
if entry.is_balanced():
    print("Entry is balanced!")
```

#### Budget
```python
budget = Budget.objects.create(
    organization=org,
    department=dept,
    name="Q1 2024 Budget",
    period_type=Budget.QUARTERLY,
    start_date=date(2024, 1, 1),
    end_date=date(2024, 3, 31),
    total_budget=Decimal('100000.00'),
    spent_amount=Decimal('25000.00')
)

# Check budget status
remaining = budget.remaining_budget
utilization = budget.utilization_percentage
```

## Permission Utilities

```python
from organizations.permissions import (
    get_user_organization_member,
    user_has_permission,
    require_permission,
    require_role,
    require_organization_member,
    PermissionMixin
)
```

### Function Decorators
```python
@require_permission('can_manage_users')
def manage_users(request):
    pass

@require_role('ADMIN')
def admin_view(request):
    pass

@require_organization_member
def org_view(request):
    pass
```

### Class-Based Views
```python
class ManageUsersView(PermissionMixin, View):
    required_permission = 'can_manage_users'

class AdminView(PermissionMixin, View):
    required_role = 'ADMIN'
```

### Check Permissions in Code
```python
# Get user's org membership
member = get_user_organization_member(request.user)

# Check specific permission
if user_has_permission(request.user, 'can_approve_expenses'):
    # User can approve expenses
    pass

# Check member permission
if member.has_permission('can_view_all_financial'):
    # Show all financial data
    pass
```

## Common Queries

### Get Organization Data
```python
# Get user's organization
member = get_user_organization_member(user)
org = member.organization
dept = member.department

# Get all members in organization
members = org.members.filter(is_active=True)

# Get all departments
departments = org.departments.filter(is_active=True)

# Get all teams in department
teams = dept.teams.filter(is_active=True)
```

### Financial Queries
```python
# Get pending expenses
pending_expenses = Expense.objects.filter(
    organization=org,
    status=Expense.PENDING
)

# Get unpaid invoices
unpaid_invoices = Invoice.objects.filter(
    organization=org,
    status__in=[Invoice.SENT, Invoice.OVERDUE]
)

# Get department expenses
dept_expenses = Expense.objects.filter(
    department=dept,
    expense_date__year=2024
)

# Get account balance
account = Account.objects.get(organization=org, code='1100')
balance = account.balance

# Get budget utilization
budgets = Budget.objects.filter(
    organization=org,
    is_active=True
)
for budget in budgets:
    print(f"{budget.name}: {budget.utilization_percentage:.1f}%")
```

## Role Permissions Matrix

| Permission | ADMIN | MANAGER | ACCOUNTANT | EMPLOYEE | VIEWER |
|-----------|-------|---------|------------|----------|--------|
| can_manage_users | ✓ | ✗ | ✗ | ✗ | ✗ |
| can_manage_roles | ✓ | ✗ | ✗ | ✗ | ✗ |
| can_view_all_financial | ✓ | ✗ | ✓ | ✗ | ✗ |
| can_manage_financial | ✓ | ✗ | ✓ | ✗ | ✗ |
| can_approve_expenses | ✓ | ✓ | ✓ | ✗ | ✗ |
| can_manage_departments | ✓ | ✗ | ✗ | ✗ | ✗ |
| can_manage_teams | ✓ | ✓ | ✗ | ✗ | ✗ |
| can_view_reports | ✓ | ✓ | ✓ | ✗ | ✓ |
| can_export_data | ✓ | ✗ | ✓ | ✗ | ✗ |

## Management Commands

```bash
# Create demo organization
python manage.py create_demo_organization

# Create demo with custom name and admin
python manage.py create_demo_organization --org-name "My Company" --admin-username myuser

# Create migrations
python manage.py makemigrations

# Run migrations
python manage.py migrate

# Check for issues
python manage.py check
```

## Admin Interface URLs

Access via `/admin/` after starting the server:

- Organizations: `/admin/organizations/organization/`
- Departments: `/admin/organizations/department/`
- Teams: `/admin/organizations/team/`
- Roles: `/admin/organizations/role/`
- Members: `/admin/organizations/organizationmember/`
- Accounts: `/admin/accounting/account/`
- Expenses: `/admin/accounting/expense/`
- Invoices: `/admin/accounting/invoice/`
- Payments: `/admin/accounting/payment/`
- Journal Entries: `/admin/accounting/journalentry/`
- Budgets: `/admin/accounting/budget/`

## Template Context Variables

Available in all templates (via context processor):

```django
{{ user_organization_member }}  {# OrganizationMember instance #}
{{ user_organization }}          {# Organization instance #}
{{ user_role }}                  {# Role instance #}
{{ user_department }}            {# Department instance #}

{# Check permissions #}
{% if user_role.can_manage_users %}
    <a href="/manage-users/">Manage Users</a>
{% endif %}

{% if user_role.can_approve_expenses %}
    <a href="/expenses/pending/">Approve Expenses</a>
{% endif %}
```

## Account Types

- **ASSET**: Cash, Accounts Receivable, Equipment
- **LIABILITY**: Accounts Payable, Loans, Credit Cards
- **EQUITY**: Owner's Equity, Retained Earnings
- **REVENUE**: Sales, Service Revenue, Interest Income
- **EXPENSE**: Salaries, Rent, Utilities, Travel

## Expense Categories

- **TRAVEL**: Flights, hotels, transportation
- **MEALS**: Meals and entertainment
- **OFFICE**: Office supplies and equipment
- **EQUIPMENT**: Computers, furniture
- **SOFTWARE**: Software licenses and subscriptions
- **TRAINING**: Training and professional development
- **OTHER**: Other expenses

## Status Values

### Expense Status
- PENDING → APPROVED → PAID (or REJECTED)

### Invoice Status
- DRAFT → SENT → PAID (or OVERDUE, CANCELLED)

## Next Steps

1. Create views for your accounting features
2. Build templates for expense submission, invoice management
3. Add report generation
4. Implement file uploads for receipts
5. Add email notifications
6. Build dashboard with financial overview
7. Add data export functionality

For detailed implementation examples, see:
- [ACCOUNTING_SYSTEM.md](ACCOUNTING_SYSTEM.md) - Complete system documentation
- [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - Integration with sign-up/sign-in
