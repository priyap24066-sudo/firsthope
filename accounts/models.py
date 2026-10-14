from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        RECRUITER = 'recruiter', 'Recruiter'
        CANDIDATE = 'candidate', 'Candidate'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CANDIDATE,
    )

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.role})"

class CandidateProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='candidate_profile'
    )
    phone = models.CharField(max_length=15, blank=True)
    location = models.CharField(max_length=100, blank=True)
    skills = models.CharField(
        max_length=255, blank=True, help_text='Comma separated, e.g. Python, Django, SQL'
    )
    experience_years = models.PositiveIntegerField(default=0)
    education = models.CharField(max_length=200, blank=True)
    about = models.TextField(blank=True)

    def __str__(self):
        return f"Candidate: {self.user.username}"


class RecruiterProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='recruiter_profile'
    )
    company_name = models.CharField(max_length=150, blank=True)
    company_website = models.URLField(blank=True)
    location = models.CharField(max_length=100, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    about_company = models.TextField(blank=True)

    def __str__(self):
        return f"Recruiter: {self.user.username}"