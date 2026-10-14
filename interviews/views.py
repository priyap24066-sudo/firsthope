from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from applications.models import Application
from applications.views import candidate_required
from jobs.views import recruiter_required

from .forms import InterviewForm
from .models import Interview


@recruiter_required
def schedule_interview(request, application_id):
    application = get_object_or_404(
        Application.objects.select_related('job', 'candidate'),
        pk=application_id,
        job__recruiter=request.user,
    )

    if application.status != Application.Status.SHORTLISTED:
        messages.error(request, 'You can schedule interviews only for shortlisted candidates.')
        return redirect('job_applicants', pk=application.job.pk)

    if request.method == 'POST':
        form = InterviewForm(request.POST)
        if form.is_valid():
            interview = form.save(commit=False)
            interview.application = application
            interview.save()
            messages.success(
                request,
                f'Interview scheduled with {application.candidate.username}.',
            )
            return redirect('recruiter_interviews')
    else:
        form = InterviewForm()

    return render(
        request,
        'interviews/schedule_form.html',
        {'form': form, 'application': application},
    )


@recruiter_required
def recruiter_interviews(request):
    interviews = Interview.objects.filter(
        application__job__recruiter=request.user
    ).select_related('application__job', 'application__candidate')
    return render(request, 'interviews/recruiter_interviews.html', {'interviews': interviews})


@recruiter_required
@require_POST
def update_interview_status(request, pk):
    interview = get_object_or_404(
        Interview, pk=pk, application__job__recruiter=request.user
    )
    new_status = request.POST.get('status')

    if interview.status != Interview.Status.SCHEDULED:
        messages.error(request, 'Only scheduled interviews can be changed.')
    elif new_status in (Interview.Status.COMPLETED, Interview.Status.CANCELLED):
        interview.status = new_status
        interview.save(update_fields=['status'])
        messages.success(request, f'Interview marked as {interview.get_status_display()}.')
    else:
        messages.error(request, 'Invalid status.')

    return redirect('recruiter_interviews')


@candidate_required
def my_interviews(request):
    interviews = Interview.objects.filter(
        application__candidate=request.user
    ).select_related('application__job')
    return render(request, 'interviews/my_interviews.html', {'interviews': interviews})