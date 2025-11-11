# Accounting System with Organizational Hierarchy

This document provides a comprehensive overview of the newly implemented accounting system with proper user roles, permissions, and organizational structure.

## Overview

The accounting system has been implemented with two new Django apps:

1. **organizations** - Manages organizational structure, roles, and permissions
2. **accounting** - Manages financial transactions, invoices, expenses, and budgets

## Architecture

### 1. Organizational Structure

#### Organization
- Top-level entity representing a company or business
- Supports hierarchical structure with parent-subsidiary relationships
- Contains contact information, address, tax ID, and registration details

#### Department
- Second-level structure within organizations
- Can have hierarchical structure (parent-child departments)
- Each department has:
  - Department head (User)
  - Budget allocation
  - Multiple teams

#### Team
- Project-based groups within departments
- Similar to Jira teams
- Each team has:
  - Team lead (User)
  - Project key (for Jira integration)
  - Budget allocation
  - Team members

### 2. User Roles & Permissions

#### Built-in Roles

The system includes 5 predefined roles:

##### ADMIN Role
Full access to all features:
- ✓ Manage users and roles
- ✓ View all financial data
- ✓ Manage financial records
- ✓ Approve expenses
- ✓ Manage departments and teams
- ✓ View reports and export data

##### MANAGER Role
Team management and expense approval:
- ✗ Cannot manage users/roles
- ✗ Cannot view all financial data
- ✗ Cannot manage financial records directly
- ✓ Can approve expenses
- ✓ Can manage teams
- ✓ Can view reports
- ✗ Cannot export data

##### ACCOUNTANT Role
Financial management and reporting:
- ✗ Cannot manage users/roles
- ✓ Can view all financial data
- ✓ Can manage financial records
- ✓ Can approve expenses
- ✗ Cannot manage departments/teams
- ✓ Can view reports
- ✓ Can export data

##### EMPLOYEE Role
Standard employee access:
- ✗ Cannot manage users/roles
- ✗ Cannot view all financial data
- ✗ Cannot manage financial records
- ✗ Cannot approve expenses
- ✗ Cannot manage departments/teams
- ✗ Cannot view reports
- ✗ Cannot export data
- ✓ Can submit personal expenses

##### VIEWER Role
Read-only access:
- ✗ Cannot manage users/roles
- ✗ Cannot view all financial data
- ✗ Cannot manage financial records
- ✗ Cannot approve expenses
- ✗ Cannot manage departments/teams
- ✓ Can view reports
- ✗ Cannot export data

#### Permission System

Each role has granular permissions:
- `can_manage_users` - Add/remove organization members
- `can_manage_roles` - Assign and modify roles
- `can_view_all_financial` - View all financial records
- `can_manage_financial` - Create/edit financial records
- `can_approve_expenses` - Approve employee expense requests
- `can_manage_departments` - Create/edit departments
- `can_manage_teams` - Create/edit teams
- `can_view_reports` - Access financial reports
- `can_export_data` - Export financial data

### 3. Models

#### Organizations App Models

1. **Organization**
   - Company/business entity
   - Fields: name, slug, description, email, phone, address, tax_id, etc.

2. **Department**
   - Organizational department
   - Fields: name, organization, head, budget_allocated, parent_department

3. **Team**
   - Project-based team
   - Fields: name, department, lead, project_key, budget_allocated

4. **Role**
   - User role with permissions
   - Fields: organization, role_type, permissions (9 boolean fields)

5. **OrganizationMember**
   - Links users to organizations with roles
   - Fields: user, organization, department, role, job_title, salary, employment dates

6. **TeamMember**
   - Links organization members to teams
   - Fields: member, team, is_lead

#### Accounting App Models

1. **Account**
   - Chart of accounts
   - Types: ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE
   - Supports hierarchical structure

2. **Expense**
   - Employee expense requests
   - Status workflow: PENDING → APPROVED → PAID
   - Categories: Travel, Meals, Office, Equipment, Software, Training, Other
   - Approval workflow with approver tracking

3. **Invoice**
   - Customer and vendor invoices
   - Types: CUSTOMER, VENDOR
   - Status: DRAFT, SENT, PAID, OVERDUE, CANCELLED
   - Supports line items, tax, discounts

4. **InvoiceLineItem**
   - Individual line items on invoices
   - Auto-calculates amount from quantity × unit_price

5. **Payment**
   - Payment records for invoices and expenses
   - Methods: Cash, Check, Credit Card, Bank Transfer, PayPal, Stripe, Other

6. **JournalEntry**
   - Double-entry bookkeeping journal entries
   - Types: Standard, Adjusting, Closing, Reversing
   - Validates that debits equal credits

7. **JournalEntryLine**
   - Individual debit/credit lines
   - Can be allocated to departments/teams

8. **Budget**
   - Budget planning for departments and teams
   - Periods: Annual, Quarterly, Monthly
   - Tracks spent amount and calculates utilization

## Usage

### 1. Creating a Demo Organization

A management command is provided to quickly set up a demo organization:

```bash
python manage.py create_demo_organization --org-name "Your Company" --admin-username admin
```

This creates:
- Organization with 3 departments (Engineering, Product, Finance)
- 3 teams (Backend, Frontend, Product Strategy)
- 5 default roles (Admin, Manager, Accountant, Employee, Viewer)
- Complete chart of accounts (Assets, Liabilities, Equity, Revenue, Expenses)
- Admin user as organization member with ADMIN role

### 2. Using Permissions in Views

#### Function-based views:

```python
from organizations.permissions import require_permission, require_role

@require_permission('can_manage_users')
def manage_users_view(request):
    # Only users with can_manage_users permission can access
    pass

@require_role('ADMIN')
def admin_only_view(request):
    # Only ADMIN role can access
    pass
```

#### Class-based views:

```python
from organizations.permissions import PermissionMixin
from django.views import View

class ManageUsersView(PermissionMixin, View):
    required_permission = 'can_manage_users'

    def get(self, request):
        # Only users with permission can access
        pass

class AdminOnlyView(PermissionMixin, View):
    required_role = 'ADMIN'

    def get(self, request):
        # Only ADMIN role can access
        pass
```

#### Checking permissions in code:

```python
from organizations.permissions import user_has_permission

if user_has_permission(request.user, 'can_approve_expenses'):
    # User can approve expenses
    pass
```

### 3. Using in Templates

The organization context is automatically available in all templates:

```django
{% if user_organization_member %}
    <p>Organization: {{ user_organization.name }}</p>
    <p>Role: {{ user_role.get_role_type_display }}</p>
    <p>Department: {{ user_department.name }}</p>

    {% if user_role.can_manage_users %}
        <a href="/manage-users/">Manage Users</a>
    {% endif %}
{% endif %}
```

### 4. Admin Interface

All models are registered in the Django admin with comprehensive interfaces:

- **Organizations Admin**: `/admin/organizations/`
  - Organization, Department, Team management
  - Role and permission configuration
  - Member management

- **Accounting Admin**: `/admin/accounting/`
  - Chart of accounts
  - Expense tracking and approval
  - Invoice management
  - Payment processing
  - Journal entries
  - Budget management

### 5. Workflow Examples

#### Expense Approval Workflow

1. **Employee submits expense**:
   ```python
   from accounting.models import Expense

   expense = Expense.objects.create(
       organization=org,
       member=org_member,
       department=department,
       title="Conference Travel",
       description="Flight and hotel for tech conference",
       category=Expense.TRAVEL,
       amount=Decimal('1500.00'),
       expense_date=date.today(),
       account=travel_expense_account,
       status=Expense.PENDING
   )
   ```

2. **Manager/Accountant approves**:
   ```python
   expense.status = Expense.APPROVED
   expense.approved_by = request.user
   expense.approved_date = timezone.now()
   expense.save()
   ```

3. **Accountant processes payment**:
   ```python
   from accounting.models import Payment

   payment = Payment.objects.create(
       organization=org,
       expense=expense,
       amount=expense.amount,
       payment_method=Payment.BANK_TRANSFER,
       payment_date=date.today(),
       processed_by=request.user
   )

   expense.status = Expense.PAID
   expense.paid_date = timezone.now()
   expense.save()
   ```

#### Invoice Creation

```python
from accounting.models import Invoice, InvoiceLineItem

# Create invoice
invoice = Invoice.objects.create(
    organization=org,
    invoice_number="INV-2024-001",
    invoice_type=Invoice.CUSTOMER,
    client_name="Acme Corp",
    client_email="billing@acme.com",
    subtotal=Decimal('10000.00'),
    tax_amount=Decimal('800.00'),
    total_amount=Decimal('10800.00'),
    issue_date=date.today(),
    due_date=date.today() + timedelta(days=30),
    status=Invoice.DRAFT
)

# Add line items
InvoiceLineItem.objects.create(
    invoice=invoice,
    description="Software Development Services",
    quantity=Decimal('100'),
    unit_price=Decimal('100.00'),
    account=service_revenue_account,
    order=1
)
```

## Database Schema

### Key Relationships

```
Organization
├── Departments
│   ├── Teams
│   │   └── TeamMembers → OrganizationMembers
│   └── Members (OrganizationMembers)
├── Roles
└── Accounts (Chart of Accounts)
    ├── Expenses
    ├── Invoices
    │   └── InvoiceLineItems
    ├── Payments
    ├── JournalEntries
    │   └── JournalEntryLines
    └── Budgets

User
├── OrganizationMembers
│   └── TeamMembers
├── Expenses (created)
├── Expenses (approved)
└── Payments (processed)
```

## Security Considerations

1. **Permission Checks**: Always use the provided decorators and permission checking functions
2. **Organization Isolation**: Ensure users can only access data from their organization
3. **Role Validation**: Validate role permissions before sensitive operations
4. **Audit Trail**: All financial records include creator/processor tracking
5. **Approval Workflow**: Expenses require approval before payment

## Next Steps

To fully implement the accounting system, consider:

1. **Views and URLs**: Create views for expense submission, invoice management, etc.
2. **Templates**: Build user-friendly interfaces for all operations
3. **Reports**: Implement financial reports (P&L, Balance Sheet, Budget vs Actual)
4. **API**: Add REST API endpoints for programmatic access
5. **Notifications**: Email notifications for expense approvals, invoice due dates
6. **File Uploads**: Handle receipt uploads for expenses
7. **Multi-currency**: Expand currency handling if needed
8. **Integration**: Connect with Jira for project-based expense tracking
9. **Dashboard**: Create overview dashboards for different roles
10. **Export**: Implement data export (CSV, PDF, Excel)

## Testing

Run tests to ensure everything is working:

```bash
# Check for model issues
python manage.py check

# Create demo data
python manage.py create_demo_organization

# Access admin interface
python manage.py runserver
# Visit http://localhost:8000/admin/
```

## Summary

The accounting system provides:

✅ **Organizational Hierarchy**: Organizations → Departments → Teams
✅ **Role-Based Access Control**: 5 roles with 9 granular permissions
✅ **Financial Management**: Accounts, Expenses, Invoices, Payments
✅ **Double-Entry Bookkeeping**: Journal entries with debit/credit tracking
✅ **Budget Planning**: Department and team budgets with utilization tracking
✅ **Approval Workflows**: Expense approval with status tracking
✅ **Multi-tenancy**: Support for organizations with subsidiaries
✅ **Audit Trail**: Complete tracking of who created/approved/processed records
✅ **Admin Interface**: Comprehensive Django admin for all operations
✅ **Permission System**: Decorators and utilities for view protection

All models are created, migrations are applied, and the system is ready to use!
