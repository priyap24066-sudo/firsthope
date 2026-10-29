from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import CandidateProfile, RecruiterProfile, User


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(
        choices=[
            (User.Role.CANDIDATE, 'Candidate (I am looking for a job)'),
            (User.Role.RECRUITER, 'Recruiter (I want to hire)'),
        ]
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'role')


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
        help_text='e.g. https://example.com'
    )

    class Meta:
        model = RecruiterProfile
        fields = ('company_name', 'company_website', 'location', 'designation', 'about_company')
        widgets = {'about_company': forms.Textarea(attrs={'rows': 4})}

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
