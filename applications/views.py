import os
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import User
from jobs.models import Job
from jobs.views import recruiter_required

from .forms import ApplicationForm
from .models import Application


def candidate_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.role != User.Role.CANDIDATE:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return login_required(wrapper)


@candidate_required
def apply_job(request, pk):
    job = get_object_or_404(Job, pk=pk, is_active=True)

    if Application.objects.filter(job=job, candidate=request.user).exists():
        messages.info(request, 'You have already applied for this job.')
        return redirect('my_applications')

    if request.method == 'POST':
        form = ApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            application = form.save(commit=False)
            application.job = job
            application.candidate = request.user
            application.save()
            messages.success(request, 'Application submitted successfully!')
            return redirect('my_applications')
    else:
        form = ApplicationForm()

    return render(request, 'applications/apply_form.html', {'form': form, 'job': job})


@candidate_required
def my_applications(request):
    applications = Application.objects.filter(
        candidate=request.user
    ).select_related('job')
    return render(
        request, 'applications/my_applications.html', {'applications': applications}
    )


@recruiter_required
def job_applicants(request, pk):
    job = get_object_or_404(Job, pk=pk, recruiter=request.user)

    applications = job.applications.select_related(
        'candidate', 'candidate__candidate_profile'
    )

    status = request.GET.get('status', '').strip()
    valid_statuses = [value for value, _ in Application.Status.choices]
    if status in valid_statuses:
        applications = applications.filter(status=status)
    else:
        status = ''

    context = {
        'job': job,
        'applications': applications,
        'current_status': status,
        'statuses': Application.Status.choices,
        'total': job.applications.count(),
    }
    return render(request, 'applications/job_applicants.html', context)


@recruiter_required
@require_POST
def update_status(request, pk):
    application = get_object_or_404(
        Application, pk=pk, job__recruiter=request.user
    )

    new_status = request.POST.get('status')
    valid_statuses = [value for value, _ in Application.Status.choices]

    if new_status in valid_statuses:
        application.status = new_status
        application.save(update_fields=['status'])
        messages.success(
            request,
            f'{application.candidate.username} marked as {application.get_status_display()}.',
        )
    else:
        messages.error(request, 'Invalid status.')

    return redirect('job_applicants', pk=application.job.pk)


@login_required
def download_resume(request, pk):
    application = get_object_or_404(
        Application.objects.select_related('job'), pk=pk
    )
    user = request.user

    allowed = (
        application.candidate_id == user.id
        or application.job.recruiter_id == user.id
        or user.is_superuser
    )
    if not allowed:
        raise PermissionDenied

    try:
        file = application.resume.open('rb')
    except FileNotFoundError:
        raise Http404('Resume file not found.')

    return FileResponse(file, filename=os.path.basename(application.resume.name))