from django.contrib import admin
from .models import (
    Account, Expense, Invoice, InvoiceLineItem,
    Payment, JournalEntry, JournalEntryLine, Budget
)
from organizations.models import Organization, OrganizationMember, Department, Team


def get_user_organizations(user):
    """Helper function to get organizations for a user"""
    if user.is_superuser:
        return Organization.objects.all()

    # Get organizations where user is a member with ADMIN role
    admin_memberships = OrganizationMember.objects.filter(
        user=user,
        role__role_type='ADMIN'
    ).select_related('organization')

    return Organization.objects.filter(
        id__in=admin_memberships.values_list('organization_id', flat=True)
    )


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'account_type', 'organization', 'balance', 'is_active']
    list_filter = ['account_type', 'is_active', 'organization', 'created_at']
    search_fields = ['code', 'name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['organization', 'parent_account']

    fieldsets = (
        ('Account Information', {
            'fields': ('organization', 'code', 'name', 'account_type', 'description')
        }),
        ('Hierarchy', {
            'fields': ('parent_account',)
        }),
        ('Balance', {
            'fields': ('balance', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Filter accounts based on user's organizations"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        user_orgs = get_user_organizations(request.user)
        return qs.filter(organization__in=user_orgs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter foreign key choices in forms"""
        if not request.user.is_superuser:
            user_orgs = get_user_organizations(request.user)
            if db_field.name == "organization":
                kwargs["queryset"] = user_orgs
            elif db_field.name == "parent_account":
                kwargs["queryset"] = Account.objects.filter(organization__in=user_orgs)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class InvoiceLineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    extra = 1
    autocomplete_fields = ['account']
    readonly_fields = ['amount']


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['title', 'member', 'department', 'category', 'amount', 'status', 'expense_date', 'submitted_date']
    list_filter = ['status', 'category', 'organization', 'department', 'expense_date', 'submitted_date']
    search_fields = ['title', 'description', 'member__user__username', 'payment_reference']
    readonly_fields = ['submitted_date', 'created_at', 'updated_at']
    autocomplete_fields = ['organization', 'member', 'department', 'team', 'account', 'approved_by']
    date_hierarchy = 'expense_date'

    fieldsets = (
        ('Expense Details', {
            'fields': ('organization', 'member', 'department', 'team', 'account')
        }),
        ('Information', {
            'fields': ('title', 'description', 'category', 'amount', 'currency', 'expense_date')
        }),
        ('Approval', {
            'fields': ('status', 'approved_by', 'approved_date', 'rejection_reason')
        }),
        ('Payment', {
            'fields': ('paid_date', 'payment_method', 'payment_reference')
        }),
        ('Attachments', {
            'fields': ('receipt_url',)
        }),
        ('Timestamps', {
            'fields': ('submitted_date', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj and obj.status in ['APPROVED', 'PAID']:
            readonly.extend(['amount', 'expense_date', 'category'])
        return readonly

    def get_queryset(self, request):
        """Filter expenses based on user's organizations"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        user_orgs = get_user_organizations(request.user)
        return qs.filter(organization__in=user_orgs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter foreign key choices in forms"""
        if not request.user.is_superuser:
            user_orgs = get_user_organizations(request.user)
            if db_field.name == "organization":
                kwargs["queryset"] = user_orgs
            elif db_field.name == "member":
                kwargs["queryset"] = OrganizationMember.objects.filter(organization__in=user_orgs)
            elif db_field.name == "department":
                kwargs["queryset"] = Department.objects.filter(organization__in=user_orgs)
            elif db_field.name == "team":
                kwargs["queryset"] = Team.objects.filter(department__organization__in=user_orgs)
            elif db_field.name == "account":
                kwargs["queryset"] = Account.objects.filter(organization__in=user_orgs)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'invoice_type', 'client_name', 'total_amount', 'status', 'issue_date', 'due_date']
    list_filter = ['status', 'invoice_type', 'organization', 'issue_date', 'due_date']
    search_fields = ['invoice_number', 'client_name', 'client_email']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['organization']
    date_hierarchy = 'issue_date'
    inlines = [InvoiceLineItemInline]

    fieldsets = (
        ('Invoice Information', {
            'fields': ('organization', 'invoice_number', 'invoice_type', 'status')
        }),
        ('Client Information', {
            'fields': ('client_name', 'client_email', 'client_address')
        }),
        ('Financial Details', {
            'fields': ('subtotal', 'tax_amount', 'discount_amount', 'total_amount', 'currency')
        }),
        ('Dates', {
            'fields': ('issue_date', 'due_date', 'paid_date')
        }),
        ('Additional Information', {
            'fields': ('notes', 'terms'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Filter invoices based on user's organizations"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        user_orgs = get_user_organizations(request.user)
        return qs.filter(organization__in=user_orgs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter organization choices in forms"""
        if db_field.name == "organization" and not request.user.is_superuser:
            kwargs["queryset"] = get_user_organizations(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(InvoiceLineItem)
class InvoiceLineItemAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'description', 'quantity', 'unit_price', 'amount', 'account']
    list_filter = ['invoice__organization', 'invoice__status']
    search_fields = ['description', 'invoice__invoice_number']
    readonly_fields = ['amount']
    autocomplete_fields = ['invoice', 'account']

    def get_queryset(self, request):
        """Filter invoice line items based on user's organizations"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        user_orgs = get_user_organizations(request.user)
        return qs.filter(invoice__organization__in=user_orgs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter foreign key choices in forms"""
        if not request.user.is_superuser:
            user_orgs = get_user_organizations(request.user)
            if db_field.name == "invoice":
                kwargs["queryset"] = Invoice.objects.filter(organization__in=user_orgs)
            elif db_field.name == "account":
                kwargs["queryset"] = Account.objects.filter(organization__in=user_orgs)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['organization', 'amount', 'payment_method', 'payment_date', 'invoice', 'expense', 'processed_by']
    list_filter = ['payment_method', 'organization', 'payment_date']
    search_fields = ['reference_number', 'notes', 'invoice__invoice_number']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['organization', 'invoice', 'expense', 'processed_by']
    date_hierarchy = 'payment_date'

    fieldsets = (
        ('Payment Information', {
            'fields': ('organization', 'invoice', 'expense')
        }),
        ('Payment Details', {
            'fields': ('amount', 'currency', 'payment_method', 'payment_date')
        }),
        ('Reference', {
            'fields': ('reference_number', 'notes', 'processed_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Filter payments based on user's organizations"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        user_orgs = get_user_organizations(request.user)
        return qs.filter(organization__in=user_orgs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter foreign key choices in forms"""
        if not request.user.is_superuser:
            user_orgs = get_user_organizations(request.user)
            if db_field.name == "organization":
                kwargs["queryset"] = user_orgs
            elif db_field.name == "invoice":
                kwargs["queryset"] = Invoice.objects.filter(organization__in=user_orgs)
            elif db_field.name == "expense":
                kwargs["queryset"] = Expense.objects.filter(organization__in=user_orgs)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class JournalEntryLineInline(admin.TabularInline):
    model = JournalEntryLine
    extra = 2
    autocomplete_fields = ['account', 'department', 'team']


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ['entry_number', 'entry_date', 'entry_type', 'description', 'organization', 'created_by']
    list_filter = ['entry_type', 'organization', 'entry_date', 'created_at']
    search_fields = ['entry_number', 'description']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['organization', 'invoice', 'expense', 'created_by']
    date_hierarchy = 'entry_date'
    inlines = [JournalEntryLineInline]

    fieldsets = (
        ('Entry Information', {
            'fields': ('organization', 'entry_number', 'entry_type', 'entry_date')
        }),
        ('Description', {
            'fields': ('description',)
        }),
        ('Source Documents', {
            'fields': ('invoice', 'expense'),
            'classes': ('collapse',)
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Filter journal entries based on user's organizations"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        user_orgs = get_user_organizations(request.user)
        return qs.filter(organization__in=user_orgs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter foreign key choices in forms"""
        if not request.user.is_superuser:
            user_orgs = get_user_organizations(request.user)
            if db_field.name == "organization":
                kwargs["queryset"] = user_orgs
            elif db_field.name == "invoice":
                kwargs["queryset"] = Invoice.objects.filter(organization__in=user_orgs)
            elif db_field.name == "expense":
                kwargs["queryset"] = Expense.objects.filter(organization__in=user_orgs)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(JournalEntryLine)
class JournalEntryLineAdmin(admin.ModelAdmin):
    list_display = ['journal_entry', 'account', 'debit_amount', 'credit_amount', 'department', 'team']
    list_filter = ['journal_entry__organization', 'account__account_type', 'department', 'team']
    search_fields = ['description', 'journal_entry__entry_number', 'account__name']
    autocomplete_fields = ['journal_entry', 'account', 'department', 'team']

    def get_queryset(self, request):
        """Filter journal entry lines based on user's organizations"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        user_orgs = get_user_organizations(request.user)
        return qs.filter(journal_entry__organization__in=user_orgs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter foreign key choices in forms"""
        if not request.user.is_superuser:
            user_orgs = get_user_organizations(request.user)
            if db_field.name == "journal_entry":
                kwargs["queryset"] = JournalEntry.objects.filter(organization__in=user_orgs)
            elif db_field.name == "account":
                kwargs["queryset"] = Account.objects.filter(organization__in=user_orgs)
            elif db_field.name == "department":
                kwargs["queryset"] = Department.objects.filter(organization__in=user_orgs)
            elif db_field.name == "team":
                kwargs["queryset"] = Team.objects.filter(department__organization__in=user_orgs)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization', 'department', 'team', 'period_type', 'total_budget', 'spent_amount', 'start_date', 'end_date', 'is_active']
    list_filter = ['period_type', 'is_active', 'organization', 'start_date']
    search_fields = ['name', 'notes']
    readonly_fields = ['created_at', 'updated_at', 'remaining_budget', 'utilization_percentage']
    autocomplete_fields = ['organization', 'department', 'team']
    date_hierarchy = 'start_date'

    fieldsets = (
        ('Budget Information', {
            'fields': ('organization', 'department', 'team', 'name', 'period_type')
        }),
        ('Period', {
            'fields': ('start_date', 'end_date')
        }),
        ('Financial', {
            'fields': ('total_budget', 'spent_amount', 'remaining_budget', 'utilization_percentage')
        }),
        ('Status', {
            'fields': ('is_active', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def remaining_budget(self, obj):
        return obj.remaining_budget
    remaining_budget.short_description = 'Remaining Budget'

    def utilization_percentage(self, obj):
        return f"{obj.utilization_percentage:.2f}%"
    utilization_percentage.short_description = 'Utilization %'

    def get_queryset(self, request):
        """Filter budgets based on user's organizations"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        user_orgs = get_user_organizations(request.user)
        return qs.filter(organization__in=user_orgs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter foreign key choices in forms"""
        if not request.user.is_superuser:
            user_orgs = get_user_organizations(request.user)
            if db_field.name == "organization":
                kwargs["queryset"] = user_orgs
            elif db_field.name == "department":
                kwargs["queryset"] = Department.objects.filter(organization__in=user_orgs)
            elif db_field.name == "team":
                kwargs["queryset"] = Team.objects.filter(department__organization__in=user_orgs)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
