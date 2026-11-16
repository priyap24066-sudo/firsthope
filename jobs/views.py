from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import User

from .forms import JobAlertForm, JobForm
from .models import Job, JobAlert, JobReport, SavedJob
from .skill_match import calculate_skill_match


# ── Helpers ──────────────────────────────────────────────────────────────────

def recruiter_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.role != User.Role.RECRUITER:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return login_required(wrapper)


# ── Job listing ───────────────────────────────────────────────────────────────

def job_list(request):
    jobs = Job.objects.filter(
        is_active=True,
        recruiter__recruiter_profile__is_verified=True,
    ).select_related('recruiter', 'recruiter__recruiter_profile')

    q = request.GET.get('q', '').strip()
    location = request.GET.get('location', '').strip()
    job_type = request.GET.get('job_type', '').strip()

    if q:
        jobs = jobs.filter(
            Q(title__icontains=q)
            | Q(company_name__icontains=q)
            | Q(skills_required__icontains=q)
        )
    if location:
        jobs = jobs.filter(location__icontains=location)
    if job_type:
        jobs = jobs.filter(job_type=job_type)

    # noindex when filters return zero results
    zero_results = jobs.count() == 0 and (q or location or job_type)

    paginator = Paginator(jobs, 6)
    page_obj = paginator.get_page(request.GET.get('page'))

    params = request.GET.copy()
    params.pop('page', None)

    context = {
        'page_obj': page_obj,
        'q': q,
        'location': location,
        'job_type': job_type,
        'job_types': Job.JobType.choices,
        'querystring': params.urlencode(),
        'total': paginator.count,
        'zero_results': zero_results,
    }
    return render(request, 'jobs/job_list.html', context)


# ── Job detail (slug URL) ─────────────────────────────────────────────────────

def job_detail(request, slug, pk):
    job = get_object_or_404(
        Job.objects.select_related('recruiter', 'recruiter__recruiter_profile'),
        pk=pk,
    )

    # Canonical redirect: if slug in URL doesn't match the job's slug, redirect
    if job.slug and slug != job.slug:
        return redirect(job.get_absolute_url(), permanent=True)

    is_recruiter_verified = getattr(
        getattr(job.recruiter, 'recruiter_profile', None), 'is_verified', False
    )
    is_owner = request.user.is_authenticated and job.recruiter == request.user
    is_admin = request.user.is_authenticated and (
        request.user.is_staff or request.user.role == User.Role.ADMIN
    )

    if (not job.is_active or not is_recruiter_verified) and not is_owner and not is_admin:
        return render(request, '404.html', status=404)

    if request.method == 'POST':
        if request.user.is_authenticated and request.user.role == User.Role.CANDIDATE:
            return report_job(request, pk=pk)
        raise PermissionDenied

    has_applied = False
    has_reported = False
    has_saved = False
    skill_match = None

    if request.user.is_authenticated and request.user.role == User.Role.CANDIDATE:
        has_applied = job.applications.filter(candidate=request.user).exists()
        has_reported = job.reports.filter(reported_by=request.user).exists()
        has_saved = SavedJob.objects.filter(user=request.user, job=job).exists()
        candidate_profile = getattr(request.user, 'candidate_profile', None)
        skill_match = calculate_skill_match(
            job.skills_required,
            candidate_profile.skills if candidate_profile else '',
        )

    # Related jobs: same company OR same city OR same type (up to 4, excluding this job)
    related_jobs = Job.objects.filter(
        is_active=True,
        recruiter__recruiter_profile__is_verified=True,
    ).exclude(pk=job.pk).filter(
        Q(company_name__iexact=job.company_name)
        | Q(location__icontains=job.location)
        | Q(job_type=job.job_type)
    ).select_related('recruiter', 'recruiter__recruiter_profile').distinct()[:4]

    return render(
        request,
        'jobs/job_detail.html',
        {
            'job': job,
            'has_applied': has_applied,
            'has_reported': has_reported,
            'has_saved': has_saved,
            'skill_match': skill_match,
            'related_jobs': related_jobs,
        },
    )


def job_detail_redirect(request, pk):
    """301 redirect from legacy /jobs/<pk>/ to /jobs/<slug>-<pk>/."""
    job = get_object_or_404(Job, pk=pk)
    return redirect(job.get_absolute_url(), permanent=True)


# ── Report ────────────────────────────────────────────────────────────────────

@login_required
def report_job(request, pk):
    if request.user.role != User.Role.CANDIDATE:
        raise PermissionDenied

    job = get_object_or_404(Job, pk=pk)
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, 'Please provide a reason for reporting this job.')
            return redirect(job.get_absolute_url())

        if JobReport.objects.filter(job=job, reported_by=request.user).exists():
            messages.warning(request, 'You have already reported this job.')
            return redirect(job.get_absolute_url())

        JobReport.objects.create(job=job, reported_by=request.user, reason=reason)
        job.refresh_from_db()
        if not job.is_active:
            messages.info(request, 'Thank you for your report. The job has been deactivated.')
            return redirect('job_list')
        messages.success(request, 'Job report submitted. Thank you for reporting.')
        return redirect(job.get_absolute_url())

    return redirect(job.get_absolute_url())


# ── Recruiter job management ──────────────────────────────────────────────────

@recruiter_required
def my_jobs(request):
    jobs = Job.objects.filter(recruiter=request.user)
    return render(request, 'jobs/my_jobs.html', {'jobs': jobs})


@recruiter_required
def job_create(request):
    profile = getattr(request.user, 'recruiter_profile', None)
    if not (profile and profile.is_verified):
        messages.warning(request, 'Upload your company proof to start posting jobs')
        return redirect('company_verification')

    if request.method == 'POST':
        form = JobForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.recruiter = request.user
            job.save()
            messages.success(request, 'Job posted successfully!')
            return redirect('my_jobs')
    else:
        company = profile.company_name if profile else ''
        form = JobForm(initial={'company_name': company})

    return render(request, 'jobs/job_form.html', {'form': form, 'heading': 'Post a Job'})


@recruiter_required
def job_edit(request, pk):
    profile = getattr(request.user, 'recruiter_profile', None)
    if not (profile and profile.is_verified):
        messages.warning(request, 'Upload your company proof to start posting jobs')
        return redirect('company_verification')

    job = get_object_or_404(Job, pk=pk, recruiter=request.user)

    if request.method == 'POST':
        form = JobForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            messages.success(request, 'Job updated successfully!')
            return redirect('my_jobs')
    else:
        form = JobForm(instance=job)

    return render(request, 'jobs/job_form.html', {'form': form, 'heading': 'Edit Job'})


@recruiter_required
def job_delete(request, pk):
    job = get_object_or_404(Job, pk=pk, recruiter=request.user)

    if request.method == 'POST':
        job.delete()
        messages.success(request, 'Job deleted.')
        return redirect('my_jobs')

    return render(request, 'jobs/job_confirm_delete.html', {'job': job})


# ── Saved jobs ────────────────────────────────────────────────────────────────

@login_required
def saved_jobs(request):
    if request.user.role != User.Role.CANDIDATE:
        raise PermissionDenied
    saves = (
        SavedJob.objects.filter(user=request.user)
        .select_related('job', 'job__recruiter', 'job__recruiter__recruiter_profile')
    )
    # Annotate application status per saved job
    from applications.models import Application
    app_map = {
        a.job_id: a.status
        for a in Application.objects.filter(candidate=request.user)
    }
    saves_with_status = []
    for save in saves:
        saves_with_status.append({
            'save': save,
            'application_status': app_map.get(save.job_id),
        })
    return render(request, 'jobs/saved_jobs.html', {'saves_with_status': saves_with_status})


@login_required
@require_POST
def toggle_save_job(request, pk):
    if request.user.role != User.Role.CANDIDATE:
        raise PermissionDenied
    job = get_object_or_404(Job, pk=pk)
    saved, created = SavedJob.objects.get_or_create(user=request.user, job=job)
    if not created:
        saved.delete()
        saved_state = False
    else:
        saved_state = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'saved': saved_state})
    action = 'saved' if saved_state else 'removed from saved'
    messages.success(request, f'"{job.title}" {action}.')
    return redirect(job.get_absolute_url())


# ── Job alerts ────────────────────────────────────────────────────────────────

@login_required
def job_alerts(request):
    if request.user.role != User.Role.CANDIDATE:
        raise PermissionDenied
    alerts = JobAlert.objects.filter(user=request.user)
    if request.method == 'POST':
        form = JobAlertForm(request.POST)
        if form.is_valid():
            alert = form.save(commit=False)
            alert.user = request.user
            alert.save()
            messages.success(request, 'Job alert created! You will receive weekly email digests.')
            return redirect('job_alerts')
    else:
        form = JobAlertForm()
    return render(request, 'jobs/job_alerts.html', {'alerts': alerts, 'form': form})


@login_required
@require_POST
def delete_job_alert(request, pk):
    if request.user.role != User.Role.CANDIDATE:
        raise PermissionDenied
    alert = get_object_or_404(JobAlert, pk=pk, user=request.user)
    alert.delete()
    messages.success(request, 'Job alert deleted.')
    return redirect('job_alerts')


# ── Programmatic landing pages ────────────────────────────────────────────────

def jobs_in_city(request, city):
    """Landing page: /jobs/in-<city>/"""
    city_display = city.replace('-', ' ').title()
    jobs = Job.objects.filter(
        is_active=True,
        recruiter__recruiter_profile__is_verified=True,
        location__icontains=city_display,
    ).select_related('recruiter', 'recruiter__recruiter_profile')

    if not jobs.exists():
        # Try partial match
        jobs = Job.objects.filter(
            is_active=True,
            recruiter__recruiter_profile__is_verified=True,
            location__icontains=city.replace('-', ' '),
        ).select_related('recruiter', 'recruiter__recruiter_profile')

    paginator = Paginator(jobs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Related cities (other locations that have jobs)
    other_cities = (
        Job.objects.filter(is_active=True, recruiter__recruiter_profile__is_verified=True)
        .exclude(location__icontains=city.replace('-', ' '))
        .values('location')
        .annotate(count=Count('pk'))
        .order_by('-count')[:8]
    )

    return render(request, 'jobs/landing_city.html', {
        'city': city_display,
        'city_slug': city,
        'page_obj': page_obj,
        'total': paginator.count,
        'other_cities': other_cities,
        'noindex': paginator.count == 0,
    })


def jobs_by_type(request, job_type):
    """Landing page: /jobs/type/<job_type>/"""
    type_map = {jt.value: jt.label for jt in Job.JobType}
    type_label = type_map.get(job_type)
    if not type_label:
        from django.http import Http404
        raise Http404

    jobs = Job.objects.filter(
        is_active=True,
        recruiter__recruiter_profile__is_verified=True,
        job_type=job_type,
    ).select_related('recruiter', 'recruiter__recruiter_profile')

    paginator = Paginator(jobs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'jobs/landing_jobtype.html', {
        'job_type': job_type,
        'type_label': type_label,
        'page_obj': page_obj,
        'total': paginator.count,
        'job_types': Job.JobType.choices,
        'noindex': paginator.count == 0,
    })
