import os
import re
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError

from .models import (
    CandidateProfile,
    RecruiterDocument,
    RecruiterProfile,
    User,
    normalize_indian_phone,
)

ALLOWED_DOC_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}
ALLOWED_CONTENT_TYPES = {'application/pdf', 'image/jpeg', 'image/png', 'image/pjpeg'}
MAX_DOC_SIZE = 5 * 1024 * 1024  # 5 MB


def validate_company_document(uploaded_file):
    if not uploaded_file:
        raise ValidationError('Please select a file to upload.')

    if uploaded_file.size > MAX_DOC_SIZE:
        raise ValidationError('File size must be under 5 MB.')

    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in ALLOWED_DOC_EXTENSIONS:
        raise ValidationError('Only PDF, JPG, and PNG files are allowed.')

    content_type = getattr(uploaded_file, 'content_type', '').lower()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError('Invalid file type. Only PDF, JPG, and PNG are allowed.')

    # Check magic bytes
    pos = uploaded_file.tell() if hasattr(uploaded_file, 'tell') else 0
    uploaded_file.seek(0)
    header = uploaded_file.read(16)
    uploaded_file.seek(pos)

    is_pdf = header.startswith(b'%PDF')
    is_jpeg = header.startswith(b'\xff\xd8\xff')
    is_png = header.startswith(b'\x89PNG\r\n\x1a\n')

    if not (is_pdf or is_jpeg or is_png):
        raise ValidationError('File signature is invalid. Please upload a genuine PDF, JPG, or PNG.')

    if is_pdf and ext != '.pdf':
        raise ValidationError('File signature is PDF but file extension does not match.')
    if is_jpeg and ext not in ('.jpg', '.jpeg'):
        raise ValidationError('File signature is JPEG but file extension does not match.')
    if is_png and ext != '.png':
        raise ValidationError('File signature is PNG but file extension does not match.')

    resolved_content_type = 'application/pdf' if is_pdf else ('image/jpeg' if is_jpeg else 'image/png')
    return ext, resolved_content_type


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        label='Email address',
        help_text='A verification code will be sent to this email.',
    )
    phone = forms.CharField(
        required=False,
        label='Mobile number (Optional)',
        help_text='10-digit Indian mobile number (optional +91).',
        widget=forms.TextInput(attrs={'placeholder': 'e.g. 9876543210'}),
    )
    role = forms.ChoiceField(
        label='I want to',
        choices=[
            (User.Role.CANDIDATE, 'Find a job (Candidate)'),
            (User.Role.RECRUITER, 'Hire talent (Recruiter)'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'role-radio'}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'phone', 'role')

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            raise forms.ValidationError('Email address is required.')
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email address already exists.')
        return email

    def clean_phone(self):
        phone_input = self.cleaned_data.get('phone', '').strip()
        if not phone_input:
            return None
        try:
            normalized = normalize_indian_phone(phone_input)
        except ValidationError as e:
            raise forms.ValidationError(e.message)

        if User.objects.filter(phone=normalized).exists():
            raise forms.ValidationError('An account with this mobile number already exists.')
        return normalized


class LoginForm(AuthenticationForm):
    username = forms.CharField(label='Username or Email')


class VerifyOTPForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        min_length=6,
        required=True,
        label='6-Digit Verification Code',
        widget=forms.TextInput(
            attrs={
                'placeholder': '123456',
                'autocomplete': 'one-time-code',
                'inputmode': 'numeric',
                'pattern': r'\d{6}',
                'autofocus': True,
            }
        ),
    )


class CandidateProfileForm(forms.ModelForm):
    class Meta:
        model = CandidateProfile
        fields = ('phone', 'location', 'skills', 'experience_years', 'education', 'about')
        widgets = {'about': forms.Textarea(attrs={'rows': 4})}


class RecruiterProfileForm(forms.ModelForm):
    company_name = forms.CharField(max_length=150, required=True, label='Company Name')
    company_website = forms.URLField(
        required=True,
        assume_scheme='https',
        label='Company Website',
        help_text='e.g. https://example.com',
    )
    company_email = forms.EmailField(
        required=True,
        label='Official Company Email',
        help_text='Official business email for verification.',
    )
    address = forms.CharField(
        required=True,
        label='Company Registered Address',
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Full street address, city, state, pincode'}),
    )

    class Meta:
        model = RecruiterProfile
        fields = (
            'company_name',
            'company_website',
            'company_email',
            'address',
            'location',
            'designation',
            'about_company',
        )
        widgets = {'about_company': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        if 'data' in kwargs and kwargs['data']:
            data = kwargs['data'].copy()
            if 'website' in data and 'company_website' not in data:
                data['company_website'] = data['website']
            kwargs['data'] = data
        elif len(args) > 0 and isinstance(args[0], dict):
            data = args[0].copy()
            if 'website' in data and 'company_website' not in data:
                data['company_website'] = data['website']
            args = (data,) + args[1:]
        super().__init__(*args, **kwargs)

    def clean_company_name(self):
        company_name = self.cleaned_data.get('company_name', '').strip()
        if not company_name:
            raise forms.ValidationError('Company name is required.')

        qs = RecruiterProfile.objects.filter(
            company_name__iexact=company_name,
            is_verified=True,
        )
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        elif self.instance and hasattr(self.instance, 'user') and self.instance.user_id:
            qs = qs.exclude(user=self.instance.user)

        if qs.exists():
            raise forms.ValidationError(
                f'A verified company with the name "{company_name}" already exists.'
            )
        return company_name

    def clean_company_website(self):
        website = self.cleaned_data.get('company_website', '').strip()
        if not website:
            raise forms.ValidationError('Website is required.')
        return website


class RecruiterDocumentUploadForm(forms.ModelForm):
    file = forms.FileField(
        required=True,
        label='Select Document',
        help_text='Allowed formats: PDF, JPG, PNG (Max 5 MB).',
    )

    class Meta:
        model = RecruiterDocument
        fields = ('document_type', 'description', 'file')
        widgets = {
            'description': forms.TextInput(
                attrs={'placeholder': 'Explain document if selecting "Other proof"'}
            )
        }

    def clean(self):
        cleaned_data = super().clean()
        doc_type = cleaned_data.get('document_type')
        description = cleaned_data.get('description', '').strip()
        file = cleaned_data.get('file')

        if doc_type == RecruiterDocument.DocType.OTHER and not description:
            self.add_error('description', 'Description is required when document type is Other.')

        if file:
            try:
                ext, resolved_content_type = validate_company_document(file)
                cleaned_data['validated_ext'] = ext
                cleaned_data['validated_content_type'] = resolved_content_type
            except ValidationError as e:
                self.add_error('file', e)

        return cleaned_data
