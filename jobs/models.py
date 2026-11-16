from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Job(models.Model):
    class JobType(models.TextChoices):
        FULL_TIME = 'full_time', 'Full Time'
        PART_TIME = 'part_time', 'Part Time'
        INTERNSHIP = 'internship', 'Internship'
        CONTRACT = 'contract', 'Contract'

    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='jobs',
    )
    title = models.CharField(max_length=150)
    slug = models.SlugField(max_length=180, blank=True, db_index=True)
    company_name = models.CharField(max_length=150)
    location = models.CharField(max_length=100)
    job_type = models.CharField(
        max_length=20, choices=JobType.choices, default=JobType.FULL_TIME
    )
    salary = models.CharField(max_length=100, blank=True, help_text='e.g. 3-5 LPA')
    skills_required = models.CharField(
        max_length=255, help_text='Comma separated, e.g. Python, Django, SQL'
    )
    description = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Soft-expiry: set when recruiter manually closes or expires. If None, treated as open.
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['is_active', '-created_at']),
            models.Index(fields=['location']),
            models.Index(fields=['job_type']),
            models.Index(fields=['slug']),
        ]

    def __str__(self):
        return f"{self.title} at {self.company_name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('job_detail', kwargs={'slug': self.slug, 'pk': self.pk})

    def skills_list(self):
        return [s.strip() for s in self.skills_required.split(',') if s.strip()]


class SavedJob(models.Model):
    """Candidates can bookmark jobs to apply later."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_jobs',
    )
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='saves')
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'job')
        ordering = ['-saved_at']

    def __str__(self):
        return f"{self.user.username} saved {self.job.title}"


class JobAlert(models.Model):
    """Candidates subscribe to keyword+location alerts for new jobs."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='job_alerts',
    )
    keyword = models.CharField(max_length=100, blank=True, help_text='Job title, skill, or company keyword')
    location = models.CharField(max_length=100, blank=True, help_text='City or region')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        parts = [p for p in [self.keyword, self.location] if p]
        return f"Alert for {self.user.username}: {' + '.join(parts) or 'All jobs'}"


class JobReport(models.Model):
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='reports',
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='job_reports',
    )
    reason = models.TextField()
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('job', 'reported_by')
        ordering = ['-created_on']

    def __str__(self):
        return f"Report on {self.job.title} by {self.reported_by.username}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            report_count = JobReport.objects.filter(job=self.job).count()
            if report_count >= 3:
                Job.objects.filter(pk=self.job_id).update(is_active=False)
                self.job.is_active = False
