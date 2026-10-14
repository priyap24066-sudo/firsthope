from django import forms
from django.utils import timezone

from .models import Interview


class InterviewForm(forms.ModelForm):
    class Meta:
        model = Interview
        fields = ('scheduled_at', 'mode', 'location_or_link', 'notes')
        widgets = {
            'scheduled_at': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'
            ),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['scheduled_at'].input_formats = ['%Y-%m-%dT%H:%M']

    def clean_scheduled_at(self):
        value = self.cleaned_data['scheduled_at']
        if value <= timezone.now():
            raise forms.ValidationError('Interview time must be in the future.')
        return value

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get('mode')
        location = cleaned.get('location_or_link', '')
        if mode == Interview.Mode.ONLINE and not location.startswith(('http://', 'https://')):
            self.add_error(
                'location_or_link',
                'For online interviews, enter a link starting with http:// or https://',
            )
        return cleaned