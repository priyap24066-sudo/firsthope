from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import User

from .forms import JobForm
from .models import Job
from django.core.paginator import Paginator
from django.db.models import Q

def recruiter_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.role != User.Role.RECRUITER:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return login_required(wrapper)


def job_list(request):
    jobs = Job.objects.filter(is_active=True)

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

    # page links-la filters maaraama irukka
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
    job = get_object_or_404(Job, pk=pk)
    if not job.is_active and job.recruiter != request.user:
        return render(request, '404.html', status=404)

    has_applied = False
    if request.user.is_authenticated and request.user.role == User.Role.CANDIDATE:
        has_applied = job.applications.filter(candidate=request.user).exists()

    return render(request, 'jobs/job_detail.html', {'job': job, 'has_applied': has_applied})


@recruiter_required
def my_jobs(request):
    jobs = Job.objects.filter(recruiter=request.user)
    return render(request, 'jobs/my_jobs.html', {'jobs': jobs})


@recruiter_required
def job_create(request):
    if request.method == 'POST':
        form = JobForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.recruiter = request.user
            job.save()
            messages.success(request, 'Job posted successfully!')
            return redirect('my_jobs')
    else:
        company = ''
        if hasattr(request.user, 'recruiter_profile'):
            company = request.user.recruiter_profile.company_name
        form = JobForm(initial={'company_name': company})

    return render(request, 'jobs/job_form.html', {'form': form, 'heading': 'Post a Job'})


@recruiter_required
def job_edit(request, pk):
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