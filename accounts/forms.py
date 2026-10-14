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
    class Meta:
        model = RecruiterProfile
        fields = ('company_name', 'company_website', 'location', 'designation', 'about_company')
        widgets = {'about_company': forms.Textarea(attrs={'rows': 4})}