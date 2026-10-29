from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import User

from .forms import JobForm
from .models import Job, JobReport


def recruiter_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.role != User.Role.RECRUITER:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return login_required(wrapper)


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

    paginator = Paginator(jobs, 5)
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
    }
    return render(request, 'jobs/job_list.html', context)


def job_detail(request, pk):
    job = get_object_or_404(Job.objects.select_related('recruiter', 'recruiter__recruiter_profile'), pk=pk)
    is_recruiter_verified = getattr(getattr(job.recruiter, 'recruiter_profile', None), 'is_verified', False)

    is_owner = (request.user.is_authenticated and job.recruiter == request.user)
    is_admin = (request.user.is_authenticated and (request.user.is_staff or request.user.role == User.Role.ADMIN))
    if (not job.is_active or not is_recruiter_verified) and not is_owner and not is_admin:
        return render(request, '404.html', status=404)

    if request.method == 'POST':
        if request.user.is_authenticated and request.user.role == User.Role.CANDIDATE:
            return report_job(request, pk)
        raise PermissionDenied

    has_applied = False
    has_reported = False
    if request.user.is_authenticated and request.user.role == User.Role.CANDIDATE:
        has_applied = job.applications.filter(candidate=request.user).exists()
        has_reported = job.reports.filter(reported_by=request.user).exists()

    return render(
        request,
        'jobs/job_detail.html',
        {
            'job': job,
            'has_applied': has_applied,
            'has_reported': has_reported,
        },
    )


@login_required
def report_job(request, pk):
    if request.user.role != User.Role.CANDIDATE:
        raise PermissionDenied

    job = get_object_or_404(Job, pk=pk)
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, 'Please provide a reason for reporting this job.')
            return redirect('job_detail', pk=pk)

        if JobReport.objects.filter(job=job, reported_by=request.user).exists():
            messages.warning(request, 'You have already reported this job.')
            return redirect('job_detail', pk=pk)

        JobReport.objects.create(
            job=job,
            reported_by=request.user,
            reason=reason,
        )
        job.refresh_from_db()
        if not job.is_active:
            messages.info(request, 'Thank you for your report. The job has been deactivated.')
            return redirect('job_list')
        messages.success(request, 'Job report submitted. Thank you for reporting.')
        return redirect('job_detail', pk=pk)

    return redirect('job_detail', pk=pk)


@recruiter_required
def my_jobs(request):
    jobs = Job.objects.filter(recruiter=request.user)
    return render(request, 'jobs/my_jobs.html', {'jobs': jobs})


@recruiter_required
def job_create(request):
    profile = getattr(request.user, 'recruiter_profile', None)
    if not (profile and profile.is_verified):
        messages.warning(request, 'Your company is pending verification by the admin.')
        return redirect('dashboard')

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
        messages.warning(request, 'Your company is pending verification by the admin.')
        return redirect('dashboard')

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
