import os

from django import forms

from .models import Application

ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx']
MAX_SIZE_MB = 2


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ('resume', 'cover_letter')
        widgets = {'cover_letter': forms.Textarea(attrs={'rows': 5})}

    def clean_resume(self):
        resume = self.cleaned_data['resume']
        ext = os.path.splitext(resume.name)[1].lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise forms.ValidationError('Only PDF, DOC or DOCX files are allowed.')
        if resume.size > MAX_SIZE_MB * 1024 * 1024:
            raise forms.ValidationError(f'File size must be under {MAX_SIZE_MB} MB.')
        return resume