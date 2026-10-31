from urllib.parse import urlparse

from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from django.utils.html import format_html

from .email_delivery import ADMIN_EMAIL_WARNING, send_email
from .models import OTPCode, RecruiterDocument, RecruiterProfile, User

FREE_EMAIL_DOMAINS = {'gmail.com', 'yahoo.com', 'outlook.com'}


def check_recruiter_domain_match(email, website):
    """
    Returns (is_flagged, warning_reason)
    """
    if not email:
        return True, 'No email'

    parts = email.split('@')
    if len(parts) != 2:
        return True, 'Invalid email'

    email_domain = parts[1].lower().strip()

    for free_domain in FREE_EMAIL_DOMAINS:
        if email_domain == free_domain or email_domain.endswith('.' + free_domain):
            return True, f'Public email ({email_domain})'

    if not website:
        return True, 'No website'

    netloc = urlparse(website).netloc.lower()
    if not netloc and '//' not in website:
        netloc = urlparse('//' + website).netloc.lower()

    netloc = netloc.split(':')[0]
    web_domain = netloc[4:] if netloc.startswith('www.') else netloc
    email_clean = email_domain[4:] if email_domain.startswith('www.') else email_domain

    if email_clean == web_domain or email_clean.endswith('.' + web_domain) or web_domain.endswith('.' + email_clean):
        return False, 'Domain match'

    return True, f'Domain mismatch ({email_domain} vs {web_domain})'


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Role & Verification', {'fields': ('role', 'phone')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Role & Verification', {'fields': ('role', 'phone')}),
    )
    list_display = ('username', 'email', 'phone', 'role', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff')


@admin.register(RecruiterProfile)
class RecruiterProfileAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'website', 'user', 'is_verified', 'domain_flag')
    list_filter = ('is_verified',)
    actions = ['verify_recruiters', 'unverify_recruiters']
    readonly_fields = ('domain_check_note',)

    @admin.display(description='Website', ordering='company_website')
    def website(self, obj):
        return obj.company_website or '-'

    @admin.display(description='Domain Flag')
    def domain_flag(self, obj):
        email = obj.user.email if obj.user else ''
        flagged, reason = check_recruiter_domain_match(email, obj.company_website)
        if flagged:
            return format_html('<span style="color:#c0392b; font-weight:bold;">⚠️ {}</span>', reason)
        return format_html('<span style="color:#27ae60;">✓ Match</span>')

    @admin.display(description='Domain Verification Note')
    def domain_check_note(self, obj):
        email = obj.user.email if obj.user else ''
        flagged, reason = check_recruiter_domain_match(email, obj.company_website)
        if flagged:
            return format_html(
                '<div style="color:#c0392b; font-weight:bold; background:#fdf2f2; padding:8px 12px; border-radius:4px; border:1px solid #f8b4b4;">'
                '⚠️ Flag: {} (Review domain authenticity before verifying)'
                '</div>',
                reason,
            )
        return format_html(
            '<div style="color:#27ae60; font-weight:bold; background:#def7ec; padding:8px 12px; border-radius:4px; border:1px solid #bcf0da;">'
            '✓ Recruiter email domain matches company website.'
            '</div>'
        )

    @admin.action(description='Verify selected recruiters')
    def verify_recruiters(self, request, queryset):
        queryset.update(is_verified=True, verified_on=timezone.now())

    @admin.action(description='Unverify selected recruiters')
    def unverify_recruiters(self, request, queryset):
        queryset.update(is_verified=False, verified_on=None)


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    list_display = ('user', 'channel', 'purpose', 'attempts', 'is_used', 'created_on', 'expires_on')
    list_filter = ('channel', 'purpose', 'is_used', 'created_on')
    search_fields = ('user__username', 'user__email')


@admin.register(RecruiterDocument)
class RecruiterDocumentAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'document_type', 'status', 'file_name', 'file_size_kb', 'uploaded_on')
    list_filter = ('status', 'document_type', 'uploaded_on')
    search_fields = ('recruiter__company_name', 'recruiter__user__username', 'file_name')
    actions = ['approve_documents', 'reject_documents']

    @admin.display(description='Company', ordering='recruiter__company_name')
    def company_name(self, obj):
        return obj.recruiter.company_name or obj.recruiter.user.username

    @admin.display(description='Size')
    def file_size_kb(self, obj):
        return f"{obj.file_size // 1024} KB"

    @admin.action(description='Approve selected documents')
    def approve_documents(self, request, queryset):
        now = timezone.now()
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'FirstHope <noreply@firsthope.com>')
        email_failed = False
        for doc in queryset:
            doc.status = RecruiterDocument.Status.APPROVED
            doc.reviewed_on = now
            doc.reviewed_by = request.user
            doc.save()

            # Approving sets RecruiterProfile.is_verified=True and verified_on=now
            profile = doc.recruiter
            profile.is_verified = True
            profile.verified_on = now
            profile.save()

            # Email recruiter
            if profile.user and profile.user.email:
                email_failed |= not send_email(
                    'FirstHope - Company Document Approved',
                    (
                        f"Hello {profile.user.username},\n\n"
                        f"Your verification document ({doc.get_document_type_display()}) has been approved by our admin team.\n"
                        f"Your recruiter account is now verified and you can post jobs on FirstHope.\n\n"
                        f"- The FirstHope Team"
                    ),
                    from_email,
                    [profile.user.email],
                )
        if email_failed:
            self.message_user(request, ADMIN_EMAIL_WARNING, level=messages.WARNING)

    @admin.action(description='Reject selected documents')
    def reject_documents(self, request, queryset):
        now = timezone.now()
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'FirstHope <noreply@firsthope.com>')
        email_failed = False
        for doc in queryset:
            note = doc.admin_note or "Document does not meet verification requirements."
            doc.status = RecruiterDocument.Status.REJECTED
            doc.admin_note = note
            doc.reviewed_on = now
            doc.reviewed_by = request.user
            doc.save()

            # If all of a recruiter's documents are rejected, is_verified goes back to False
            profile = doc.recruiter
            approved_exists = profile.documents.filter(status=RecruiterDocument.Status.APPROVED).exists()
            if not approved_exists:
                profile.is_verified = False
                profile.save()

            # Email recruiter
            if profile.user and profile.user.email:
                email_failed |= not send_email(
                    'FirstHope - Company Document Status Update',
                    (
                        f"Hello {profile.user.username},\n\n"
                        f"Your verification document ({doc.get_document_type_display()}) was reviewed and rejected.\n"
                        f"Reason: {note}\n\n"
                        f"Please submit a valid proof document from your Company Verification page.\n\n"
                        f"- The FirstHope Team"
                    ),
                    from_email,
                    [profile.user.email],
                )
        if email_failed:
            self.message_user(request, ADMIN_EMAIL_WARNING, level=messages.WARNING)
