import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Exists, OuterRef
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        RECRUITER = 'recruiter', 'Recruiter'
        CANDIDATE = 'candidate', 'Candidate'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CANDIDATE,
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        unique=True,
        # Deprecated: retained to preserve existing database data; no longer used.
    )

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.email.strip().lower()
            existing = User.objects.filter(email__iexact=self.email)
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            if existing.exclude(
                pk__in=never_verified_users().values('pk'),
            ).exists():
                raise ValidationError({
                    'email': 'This email is already registered. Sign in instead.'
                })

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Role.ADMIN
        if not self.email and self.username:
            self.email = f"{self.username}@example.com"
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.role})"


class CandidateProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='candidate_profile'
    )
    phone = models.CharField(
        max_length=15,
        blank=True,
        # Deprecated: retained to preserve existing database data; no longer used.
    )
    location = models.CharField(max_length=100, blank=True)
    skills = models.CharField(
        max_length=255, blank=True, help_text='Comma separated, e.g. Python, Django, SQL'
    )
    experience_years = models.PositiveIntegerField(default=0)
    education = models.CharField(max_length=200, blank=True)
    about = models.TextField(blank=True)

    def __str__(self):
        return f"Candidate: {self.user.username}"


class RecruiterProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='recruiter_profile'
    )
    company_name = models.CharField(max_length=150, blank=True)
    company_slug = models.SlugField(max_length=180, blank=True, db_index=True)
    company_website = models.URLField(blank=True)
    company_email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    location = models.CharField(max_length=100, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    about_company = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)
    verified_on = models.DateTimeField(null=True, blank=True)

    @property
    def website(self):
        return self.company_website

    @website.setter
    def website(self, value):
        self.company_website = value

    def save(self, *args, **kwargs):
        if self.company_name and not self.company_slug:
            self.company_slug = slugify(self.company_name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        if self.company_slug:
            return reverse('company_profile', kwargs={'slug': self.company_slug})
        return reverse('company_profile', kwargs={'slug': f'company-{self.pk}'})

    def clean(self):
        super().clean()
        if self.company_name:
            qs = RecruiterProfile.objects.filter(
                company_name__iexact=self.company_name.strip(),
                is_verified=True,
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            elif self.user_id:
                qs = qs.exclude(user_id=self.user_id)
            if qs.exists():
                raise ValidationError({
                    'company_name': f'A verified company with the name "{self.company_name}" already exists.'
                })

    def has_required_details(self):
        return bool(
            self.company_name.strip()
            and self.company_website.strip()
            and (self.company_email.strip() or (self.user and self.user.email))
            and (self.address.strip() or self.location.strip())
        )

    def __str__(self):
        return f"Recruiter: {self.user.username} ({self.company_name or 'No company'})"


class OTPCode(models.Model):
    class Channel(models.TextChoices):
        EMAIL = 'email', 'Email'

    class Purpose(models.TextChoices):
        REGISTER = 'register', 'Register'
        LOGIN = 'login', 'Login'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='otp_codes',
    )
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.EMAIL)
    code_hash = models.CharField(max_length=128)
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    created_on = models.DateTimeField(auto_now_add=True)
    expires_on = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_on']

    @classmethod
    def generate_code(cls):
        return f"{secrets.randbelow(1000000):06d}"

    @classmethod
    def can_resend(cls, user, purpose):
        now = timezone.now()
        # Cooldown: 60 seconds
        last_otp = cls.objects.filter(user=user, purpose=purpose).first()
        if last_otp and (now - last_otp.created_on).total_seconds() < 60:
            remaining = int(60 - (now - last_otp.created_on).total_seconds())
            return False, f"Please wait {remaining} seconds before requesting a new code."

        # Rate limit: at most 5 per hour per user
        one_hour_ago = now - timedelta(hours=1)
        hourly_count = cls.objects.filter(user=user, created_on__gte=one_hour_ago).count()
        if hourly_count >= 5:
            return False, "Maximum OTP requests reached for this hour. Please try again later."

        return True, ""

    @classmethod
    def create_otp(cls, user, purpose, channel=Channel.EMAIL):
        raw_code = cls.generate_code()
        now = timezone.now()
        expires = now + timedelta(minutes=10)
        otp = cls.objects.create(
            user=user,
            channel=channel,
            code_hash=make_password(raw_code),
            purpose=purpose,
            expires_on=expires,
        )
        return otp, raw_code

    def verify(self, raw_code):
        now = timezone.now()
        if self.is_used:
            return False, 'This OTP has already been used.'
        if now > self.expires_on:
            self.is_used = True
            self.save(update_fields=['is_used'])
            return False, 'This OTP has expired. Please request a new one.'
        if self.attempts >= 5:
            self.is_used = True
            self.save(update_fields=['is_used'])
            return False, 'Too many failed attempts. This OTP has been invalidated.'

        if check_password(raw_code.strip(), self.code_hash):
            self.is_used = True
            self.save(update_fields=['is_used'])
            return True, 'Verified successfully.'
        else:
            self.attempts += 1
            if self.attempts >= 5:
                self.is_used = True
            self.save(update_fields=['attempts', 'is_used'])
            remaining = 5 - self.attempts
            if remaining > 0:
                return False, f'Invalid OTP. {remaining} attempt{"s" if remaining > 1 else ""} remaining.'
            return False, 'Too many failed attempts. This OTP has been invalidated.'


def never_verified_users():
    successful_registration_otp = OTPCode.objects.filter(
        user_id=OuterRef('pk'),
        purpose=OTPCode.Purpose.REGISTER,
        is_used=True,
    )
    return User.objects.filter(is_active=False).annotate(
        has_verified_registration=Exists(successful_registration_otp),
    ).filter(has_verified_registration=False)


class RecruiterDocument(models.Model):
    class DocType(models.TextChoices):
        REGISTRATION = 'registration_cert', 'Company registration certificate'
        GST = 'gst_cert', 'GST certificate'
        MSME = 'msme_cert', 'Udyam/MSME certificate'
        LICENSE = 'business_license', 'Business licence'
        OTHER = 'other', 'Other proof'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    recruiter = models.ForeignKey(
        RecruiterProfile,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    document_type = models.CharField(max_length=50, choices=DocType.choices)
    description = models.CharField(max_length=255, blank=True)
    file_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    file_data = models.BinaryField()
    file_size = models.PositiveIntegerField()
    uploaded_on = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    admin_note = models.TextField(blank=True)
    reviewed_on = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_documents',
    )

    class Meta:
        ordering = ['-uploaded_on']

    def clean(self):
        super().clean()
        if self.document_type == self.DocType.OTHER and not self.description.strip():
            raise ValidationError({'description': 'Description is required when document type is Other.'})

    def __str__(self):
        return f"{self.get_document_type_display()} for {self.recruiter.company_name} ({self.get_status_display()})"
