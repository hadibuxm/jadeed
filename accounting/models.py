from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
from organizations.models import Organization, Department, Team, OrganizationMember


class Account(models.Model):
    """
    Chart of Accounts - defines all account types
    """
    ASSET = 'ASSET'
    LIABILITY = 'LIABILITY'
    EQUITY = 'EQUITY'
    REVENUE = 'REVENUE'
    EXPENSE = 'EXPENSE'

    ACCOUNT_TYPE_CHOICES = [
        (ASSET, 'Asset'),
        (LIABILITY, 'Liability'),
        (EQUITY, 'Equity'),
        (REVENUE, 'Revenue'),
        (EXPENSE, 'Expense'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='accounts'
    )
    code = models.CharField(max_length=20, help_text="Account code (e.g., 1000, 2000)")
    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
    description = models.TextField(blank=True)

    # Hierarchical structure
    parent_account = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sub_accounts'
    )

    # Current balance
    balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['organization', 'code']
        unique_together = ['organization', 'code']
        verbose_name = 'Account'
        verbose_name_plural = 'Accounts'

    def __str__(self):
        return f"{self.code} - {self.name}"


class Expense(models.Model):
    """
    Employee expense requests and tracking
    """
    PENDING = 'PENDING'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
    PAID = 'PAID'

    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
        (PAID, 'Paid'),
    ]

    TRAVEL = 'TRAVEL'
    MEALS = 'MEALS'
    OFFICE = 'OFFICE'
    EQUIPMENT = 'EQUIPMENT'
    SOFTWARE = 'SOFTWARE'
    TRAINING = 'TRAINING'
    OTHER = 'OTHER'

    CATEGORY_CHOICES = [
        (TRAVEL, 'Travel'),
        (MEALS, 'Meals & Entertainment'),
        (OFFICE, 'Office Supplies'),
        (EQUIPMENT, 'Equipment'),
        (SOFTWARE, 'Software & Subscriptions'),
        (TRAINING, 'Training & Development'),
        (OTHER, 'Other'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='expenses'
    )
    member = models.ForeignKey(
        OrganizationMember,
        on_delete=models.CASCADE,
        related_name='expenses'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses'
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses'
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name='expenses',
        help_text="Expense account to charge"
    )

    # Expense details
    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(max_length=3, default='USD')

    # Dates
    expense_date = models.DateField()
    submitted_date = models.DateTimeField(auto_now_add=True)

    # Approval workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_expenses'
    )
    approved_date = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    # Payment tracking
    paid_date = models.DateTimeField(null=True, blank=True)
    payment_method = models.CharField(max_length=50, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)

    # Attachments
    receipt_url = models.URLField(blank=True, help_text="URL to receipt or invoice")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-expense_date', '-created_at']
        verbose_name = 'Expense'
        verbose_name_plural = 'Expenses'

    def __str__(self):
        return f"{self.title} - {self.member.user.username} - ${self.amount}"


class Invoice(models.Model):
    """
    Invoices for billing customers or from vendors
    """
    DRAFT = 'DRAFT'
    SENT = 'SENT'
    PAID = 'PAID'
    OVERDUE = 'OVERDUE'
    CANCELLED = 'CANCELLED'

    STATUS_CHOICES = [
        (DRAFT, 'Draft'),
        (SENT, 'Sent'),
        (PAID, 'Paid'),
        (OVERDUE, 'Overdue'),
        (CANCELLED, 'Cancelled'),
    ]

    CUSTOMER = 'CUSTOMER'
    VENDOR = 'VENDOR'

    TYPE_CHOICES = [
        (CUSTOMER, 'Customer Invoice'),
        (VENDOR, 'Vendor Invoice'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='invoices'
    )
    invoice_number = models.CharField(max_length=50, unique=True)
    invoice_type = models.CharField(max_length=20, choices=TYPE_CHOICES)

    # Customer/Vendor info
    client_name = models.CharField(max_length=255)
    client_email = models.EmailField()
    client_address = models.TextField(blank=True)

    # Financial details
    subtotal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    tax_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    discount_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    currency = models.CharField(max_length=3, default='USD')

    # Dates
    issue_date = models.DateField()
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)

    # Notes
    notes = models.TextField(blank=True)
    terms = models.TextField(blank=True, help_text="Payment terms and conditions")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-issue_date', '-created_at']
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'

    def __str__(self):
        return f"{self.invoice_number} - {self.client_name} - ${self.total_amount}"

    def calculate_total(self):
        """Calculate total from subtotal, tax, and discount"""
        return self.subtotal + self.tax_amount - self.discount_amount


class InvoiceLineItem(models.Model):
    """
    Individual line items on an invoice
    """
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='line_items'
    )
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    # Account to post to
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name='invoice_line_items'
    )

    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['invoice', 'order']
        verbose_name = 'Invoice Line Item'
        verbose_name_plural = 'Invoice Line Items'

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.description}"

    def save(self, *args, **kwargs):
        """Auto-calculate amount from quantity * unit_price"""
        self.amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class Payment(models.Model):
    """
    Payment records for invoices and expenses
    """
    CASH = 'CASH'
    CHECK = 'CHECK'
    CREDIT_CARD = 'CREDIT_CARD'
    BANK_TRANSFER = 'BANK_TRANSFER'
    PAYPAL = 'PAYPAL'
    STRIPE = 'STRIPE'
    OTHER = 'OTHER'

    PAYMENT_METHOD_CHOICES = [
        (CASH, 'Cash'),
        (CHECK, 'Check'),
        (CREDIT_CARD, 'Credit Card'),
        (BANK_TRANSFER, 'Bank Transfer'),
        (PAYPAL, 'PayPal'),
        (STRIPE, 'Stripe'),
        (OTHER, 'Other'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='payments'
    )
    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='payments'
    )

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(max_length=3, default='USD')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_date = models.DateField()

    # Reference information
    reference_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    # Processing
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='processed_payments'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-payment_date', '-created_at']
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'

    def __str__(self):
        related = self.invoice or self.expense
        return f"Payment ${self.amount} - {related}"


class JournalEntry(models.Model):
    """
    General ledger journal entries for double-entry bookkeeping
    """
    STANDARD = 'STANDARD'
    ADJUSTING = 'ADJUSTING'
    CLOSING = 'CLOSING'
    REVERSING = 'REVERSING'

    ENTRY_TYPE_CHOICES = [
        (STANDARD, 'Standard'),
        (ADJUSTING, 'Adjusting'),
        (CLOSING, 'Closing'),
        (REVERSING, 'Reversing'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='journal_entries'
    )
    entry_number = models.CharField(max_length=50)
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPE_CHOICES, default=STANDARD)
    entry_date = models.DateField()
    description = models.TextField()

    # Reference to source documents
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='journal_entries'
    )
    expense = models.ForeignKey(
        Expense,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='journal_entries'
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_journal_entries'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-entry_date', '-created_at']
        unique_together = ['organization', 'entry_number']
        verbose_name = 'Journal Entry'
        verbose_name_plural = 'Journal Entries'

    def __str__(self):
        return f"{self.entry_number} - {self.entry_date} - {self.description}"

    def is_balanced(self):
        """Check if debits equal credits"""
        debits = sum(line.debit_amount for line in self.lines.all())
        credits = sum(line.credit_amount for line in self.lines.all())
        return debits == credits


class JournalEntryLine(models.Model):
    """
    Individual debit/credit lines in a journal entry
    """
    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.CASCADE,
        related_name='lines'
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name='journal_entry_lines'
    )
    description = models.CharField(max_length=255, blank=True)

    debit_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    credit_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    # Optional department/team allocation
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='journal_lines'
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='journal_lines'
    )

    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['journal_entry', 'order']
        verbose_name = 'Journal Entry Line'
        verbose_name_plural = 'Journal Entry Lines'

    def __str__(self):
        return f"{self.journal_entry.entry_number} - {self.account.name}"


class Budget(models.Model):
    """
    Budget planning for departments and teams
    """
    ANNUAL = 'ANNUAL'
    QUARTERLY = 'QUARTERLY'
    MONTHLY = 'MONTHLY'

    PERIOD_CHOICES = [
        (ANNUAL, 'Annual'),
        (QUARTERLY, 'Quarterly'),
        (MONTHLY, 'Monthly'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='budgets'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='budgets'
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='budgets'
    )

    name = models.CharField(max_length=255)
    period_type = models.CharField(max_length=20, choices=PERIOD_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()

    total_budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    spent_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Budget'
        verbose_name_plural = 'Budgets'

    def __str__(self):
        entity = self.team or self.department or self.organization
        return f"{entity} - {self.name} ({self.start_date} to {self.end_date})"

    @property
    def remaining_budget(self):
        """Calculate remaining budget"""
        return self.total_budget - self.spent_amount

    @property
    def utilization_percentage(self):
        """Calculate budget utilization percentage"""
        if self.total_budget > 0:
            return (self.spent_amount / self.total_budget) * 100
        return 0
