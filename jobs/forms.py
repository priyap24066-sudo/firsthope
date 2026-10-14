from django import forms

from .models import Job


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = (
            'title', 'company_name', 'location', 'job_type',
            'salary', 'skills_required', 'description', 'is_active',
        )
        widgets = {'description': forms.Textarea(attrs={'rows': 6})}