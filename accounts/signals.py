from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import CandidateProfile, RecruiterProfile, User


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.role == User.Role.CANDIDATE:
        CandidateProfile.objects.create(user=instance)
    elif instance.role == User.Role.RECRUITER:
        RecruiterProfile.objects.create(user=instance)