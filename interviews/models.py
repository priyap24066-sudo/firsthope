from django.db import models

from applications.models import Application


class Interview(models.Model):
    class Mode(models.TextChoices):
        ONLINE = 'online', 'Online'
        IN_PERSON = 'in_person', 'In Person'
        PHONE = 'phone', 'Phone'

    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name='interviews'
    )
    scheduled_at = models.DateTimeField()
    mode = models.CharField(max_length=20, choices=Mode.choices, default=Mode.ONLINE)
    location_or_link = models.CharField(
        max_length=255, help_text='Meeting link, office address or phone number'
    )
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.SCHEDULED
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['scheduled_at']

    def __str__(self):
        return f"{self.application.candidate.username} - {self.application.job.title}"