# These methods need to be added to the respective admin classes

# For InvoiceAdmin (after line 168):
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
