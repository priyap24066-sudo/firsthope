from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import User
from applications.models import Application
from interviews.models import Interview
from jobs.models import Job


def status_counts(applications):
    return applications.aggregate(
        total=Count('id'),
        applied=Count('id', filter=Q(status=Application.Status.APPLIED)),
        shortlisted=Count('id', filter=Q(status=Application.Status.SHORTLISTED)),
        rejected=Count('id', filter=Q(status=Application.Status.REJECTED)),
        hired=Count('id', filter=Q(status=Application.Status.HIRED)),
    )


@login_required
def dashboard(request):
    if request.user.role == User.Role.RECRUITER:
        return recruiter_dashboard(request)
    if request.user.role == User.Role.CANDIDATE:
        return candidate_dashboard(request)
    return redirect('admin:index')


def recruiter_dashboard(request):
    user = request.user
    jobs = Job.objects.filter(recruiter=user)
    applications = Application.objects.filter(job__recruiter=user)

    upcoming_interviews = Interview.objects.filter(
        application__job__recruiter=user,
        status=Interview.Status.SCHEDULED,
        scheduled_at__gte=timezone.now(),
    ).select_related('application__job', 'application__candidate')[:5]

    context = {
        'total_jobs': jobs.count(),
        'active_jobs': jobs.filter(is_active=True).count(),
        'stats': status_counts(applications),
        'upcoming_interviews': upcoming_interviews,
        'recent_applications': applications.select_related('job', 'candidate')[:5],
        'job_stats': jobs.annotate(
            app_count=Count('applications')
        ).order_by('-app_count', '-created_at')[:5],
    }
    return render(request, 'dashboard/recruiter_dashboard.html', context)


def candidate_dashboard(request):
    user = request.user
    applications = Application.objects.filter(candidate=user)
    applied_job_ids = applications.values_list('job_id', flat=True)

    recommended = Job.objects.none()
    profile = getattr(user, 'candidate_profile', None)
    if profile and profile.skills:
        skills = [s.strip() for s in profile.skills.split(',') if s.strip()]
        query = Q()
        for skill in skills:
            query |= Q(skills_required__icontains=skill)
        recommended = (
            Job.objects.filter(is_active=True)
            .filter(query)
            .exclude(id__in=applied_job_ids)[:5]
        )

    upcoming_interviews = Interview.objects.filter(
        application__candidate=user,
        status=Interview.Status.SCHEDULED,
        scheduled_at__gte=timezone.now(),
    ).select_related('application__job')[:5]

    context = {
        'stats': status_counts(applications),
        'upcoming_interviews': upcoming_interviews,
        'recent_applications': applications.select_related('job')[:5],
        'recommended_jobs': recommended,
    }
    return render(request, 'dashboard/candidate_dashboard.html', context)