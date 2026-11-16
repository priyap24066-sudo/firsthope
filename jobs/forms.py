from django import forms

from .models import Job, JobAlert


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = (
            'title', 'company_name', 'location', 'job_type',
            'salary', 'skills_required', 'description', 'is_active',
        )
        widgets = {'description': forms.Textarea(attrs={'rows': 6})}


class JobAlertForm(forms.ModelForm):
    class Meta:
        model = JobAlert
        fields = ('keyword', 'location')
        widgets = {
            'keyword': forms.TextInput(attrs={'placeholder': 'e.g. Python Developer, Marketing'}),
            'location': forms.TextInput(attrs={'placeholder': 'e.g. Chennai, Coimbatore'}),
        }
        help_texts = {
            'keyword': 'Job title, skill, or company name',
            'location': 'City or region (optional)',
        }
