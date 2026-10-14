import os

from rest_framework import serializers

from applications.forms import ALLOWED_EXTENSIONS, MAX_SIZE_MB
from applications.models import Application
from interviews.models import Interview
from jobs.models import Job
from django.urls import reverse

class JobSerializer(serializers.ModelSerializer):
    recruiter = serializers.ReadOnlyField(source='recruiter.username')
    job_type_display = serializers.ReadOnlyField(source='get_job_type_display')
    skills = serializers.ListField(
        child=serializers.CharField(), source='skills_list', read_only=True
    )

    class Meta:
        model = Job
        fields = (
            'id', 'recruiter', 'title', 'company_name', 'location',
            'job_type', 'job_type_display', 'salary', 'skills_required',
            'skills', 'description', 'is_active', 'created_at',
        )
        read_only_fields = ('id', 'created_at')


class ApplicationSerializer(serializers.ModelSerializer):
    candidate = serializers.ReadOnlyField(source='candidate.username')
    job_title = serializers.ReadOnlyField(source='job.title')
    status_display = serializers.ReadOnlyField(source='get_status_display')

    class Meta:
        model = Application
        fields = (
            'id', 'job', 'job_title', 'candidate', 'resume', 'cover_letter',
            'status', 'status_display', 'applied_at',
        )
        read_only_fields = ('id', 'status', 'applied_at')
        validators = []

    def validate_job(self, job):
        if not job.is_active:
            raise serializers.ValidationError('This job is closed.')
        return job

    def validate_resume(self, resume):
        ext = os.path.splitext(resume.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise serializers.ValidationError('Only PDF, DOC or DOCX files are allowed.')
        if resume.size > MAX_SIZE_MB * 1024 * 1024:
            raise serializers.ValidationError(f'File size must be under {MAX_SIZE_MB} MB.')
        return resume

    def validate(self, attrs):
        request = self.context['request']
        if Application.objects.filter(job=attrs['job'], candidate=request.user).exists():
            raise serializers.ValidationError('You have already applied for this job.')
        return attrs
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.pk and instance.resume:
            url = reverse('download_resume', args=[instance.pk])
            request = self.context.get('request')
            data['resume'] = request.build_absolute_uri(url) if request else url
        return data

class InterviewSerializer(serializers.ModelSerializer):
    job_title = serializers.ReadOnlyField(source='application.job.title')
    candidate = serializers.ReadOnlyField(source='application.candidate.username')
    mode_display = serializers.ReadOnlyField(source='get_mode_display')
    status_display = serializers.ReadOnlyField(source='get_status_display')

    class Meta:
        model = Interview
        fields = (
            'id', 'application', 'job_title', 'candidate', 'scheduled_at',
            'mode', 'mode_display', 'location_or_link', 'notes',
            'status', 'status_display',
        )
        read_only_fields = fields