import math
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    ACTIVE_ACCOUNT_ERROR,
    CandidateProfileForm,
    LoginForm,
    RecruiterDocumentUploadForm,
    RecruiterProfileForm,
    RegisterForm,
    VerifyOTPForm,
)
from .models import (
    CandidateProfile,
    OTPCode,
    RecruiterDocument,
    RecruiterProfile,
    User,
    never_verified_users,
)
from .email_delivery import (
    EMAIL_SEND_FAILURE_MESSAGE,
    email_delivery_available,
    log_email_delivery_failure,
)
from .otp_sender import send_email_otp
from .ratelimit import ratelimit_view


from jobs.models import Job

VERIFICATION_EMAIL_FAILURE_MESSAGE = (
    'We could not send the verification email right now. Please check the email address '
    'and try again in a minute.'
)


def home(request):
    active_verified_jobs = Job.objects.filter(
        is_active=True,
        recruiter__recruiter_profile__is_verified=True,
    ).select_related('recruiter', 'recruiter__recruiter_profile')
    latest_jobs = active_verified_jobs[:6]
    hiring_companies = active_verified_jobs.values('company_name').annotate(
        open_job_count=Count('pk'),
    ).order_by('-open_job_count', 'company_name')[:4]
    company_colors = ('blue', 'green', 'purple', 'orange', 'teal')
    hiring_companies = [
        {
            **company,
            'initial': company['company_name'][:1].upper(),
            'color_class': company_colors[
                sum(ord(character) for character in company['company_name'].lower())
                % len(company_colors)
            ],
        }
        for company in hiring_companies
    ]
    job_type_counts = dict(
        active_verified_jobs.order_by().values_list('job_type').annotate(
            open_job_count=Count('pk'),
        )
    )
    job_type_cards = [
        {'value': 'full_time', 'label': 'Full Time', 'icon': 'briefcase'},
        {'value': 'internship', 'label': 'Internship', 'icon': 'academic-cap'},
        {'value': 'part_time', 'label': 'Part Time', 'icon': 'clock'},
        {'value': 'contract', 'label': 'Contract', 'icon': 'document'},
    ]
    for job_type in job_type_cards:
        job_type['open_job_count'] = job_type_counts.get(job_type['value'], 0)

    return render(request, 'home.html', {
        'latest_jobs': latest_jobs,
        'hiring_companies': hiring_companies,
        'job_type_cards': job_type_cards,
        'otp_required': settings.REGISTER_OTP_REQUIRED,
    })


@ratelimit_view('register', limit=10, window_seconds=60)
def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']
            email_sent = not settings.REGISTER_OTP_REQUIRED
            try:
                with transaction.atomic():
                    conflicts = User.objects.filter(
                        Q(username__iexact=username) | Q(email__iexact=email),
                    ).exclude(pk__in=never_verified_users().values('pk'))
                    if conflicts.exists():
                        form.add_error(
                            'email',
                            ACTIVE_ACCOUNT_ERROR,
                        )
                    else:
                        never_verified_users().filter(
                            Q(username__iexact=username) | Q(email__iexact=email),
                        ).delete()
                        user = form.save(commit=False)
                        user.is_active = not settings.REGISTER_OTP_REQUIRED
                        user.save()

                        if settings.REGISTER_OTP_REQUIRED:
                            _, raw_code = OTPCode.create_otp(
                                user=user,
                                purpose=OTPCode.Purpose.REGISTER,
                            )
                            try:
                                email_sent = send_email_otp(
                                    user,
                                    raw_code,
                                    purpose='register',
                                )
                            except Exception as exc:
                                log_email_delivery_failure(exc)
                                email_sent = False

                            if not email_sent:
                                transaction.set_rollback(True)
            except IntegrityError as exc:
                log_email_delivery_failure(exc)
                form.add_error(
                    'email',
                    ACTIVE_ACCOUNT_ERROR,
                )

            if form.errors:
                return render(request, 'accounts/register.html', {
                    'form': form,
                    'otp_required': settings.REGISTER_OTP_REQUIRED,
                })

            if settings.REGISTER_OTP_REQUIRED and not email_sent:
                form.add_error(None, VERIFICATION_EMAIL_FAILURE_MESSAGE)
                return render(request, 'accounts/register.html', {
                    'form': form,
                    'otp_required': settings.REGISTER_OTP_REQUIRED,
                })

            if settings.REGISTER_OTP_REQUIRED:
                request.session['pending_otp_user'] = user.id
                request.session['otp_purpose'] = OTPCode.Purpose.REGISTER
                request.session['otp_send_succeeded'] = True
                messages.success(
                    request,
                    f'A code was sent to {user.email}. Please verify below.',
                )
                return redirect('verify_otp')

            login(request, user)
            messages.success(request, 'Account created successfully. Welcome to FirstHope!')
            return redirect('dashboard')
    else:
        form = RegisterForm(initial={
            'username': request.GET.get('username', ''),
            'email': request.GET.get('email', ''),
        })

    return render(request, 'accounts/register.html', {
        'form': form,
        'otp_required': settings.REGISTER_OTP_REQUIRED,
    })


@ratelimit_view('verify_otp', limit=15, window_seconds=60)
def verify_otp(request):
    user_id = request.session.get('pending_otp_user')
    purpose = request.session.get('otp_purpose', OTPCode.Purpose.REGISTER)

    if not user_id:
        for key in ('otp_purpose', 'otp_send_succeeded'):
            request.session.pop(key, None)
        messages.info(request, 'Your verification session expired. Please register again.')
        return redirect('register')

    user = User.objects.filter(pk=user_id).first()
    if user is None:
        for key in ('pending_otp_user', 'otp_purpose', 'otp_send_succeeded'):
            request.session.pop(key, None)
        messages.info(request, 'Your verification session expired. Please register again.')
        return redirect('register')

    if request.method == 'POST':
        form = VerifyOTPForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Please enter a valid 6-digit verification code.')
            return redirect('verify_otp')

        active_otp = OTPCode.objects.filter(
            user=user,
            purpose=purpose,
            is_used=False,
        ).first()
        if not active_otp:
            messages.error(request, 'No active code was found. Please request a new one.')
            return redirect('verify_otp')

        success, msg = active_otp.verify(form.cleaned_data['code'])
        if success:
            for key in (
                'pending_otp_user',
                'otp_purpose',
                'otp_send_succeeded',
            ):
                request.session.pop(key, None)

            if purpose == OTPCode.Purpose.REGISTER:
                user.is_active = True
                user.save(update_fields=['is_active'])
                login(request, user)
                messages.success(request, 'Email verified successfully! Welcome to FirstHope.')
                return redirect('dashboard')
            login(request, user)
            messages.success(request, 'Verification successful.')
            next_url = request.GET.get('next') or 'dashboard'
            return redirect(next_url)

        messages.error(request, msg)
        return redirect('verify_otp')
    else:
        form = VerifyOTPForm()

    masked_target = _mask_email(user.email)

    last_otp = OTPCode.objects.filter(user=user, purpose=purpose).first()
    cooldown_seconds = 0
    if last_otp:
        elapsed = (timezone.now() - last_otp.created_on).total_seconds()
        cooldown_seconds = max(0, math.ceil(60 - elapsed))

    context = {
        'form': form,
        'user_obj': user,
        'purpose': purpose,
        'target': masked_target,
        'last_send_succeeded': request.session.get('otp_send_succeeded') is True,
        'cooldown_seconds': cooldown_seconds,
    }
    return render(request, 'accounts/verify_otp.html', context)


def _mask_email(email):
    local, separator, domain = email.partition('@')
    if not separator:
        return '***'
    if len(local) > 1:
        masked_local = f'{local[0]}***{local[-1]}'
    else:
        masked_local = f'{local}***'
    return f'{masked_local}@{domain}'


@ratelimit_view('resend_otp', limit=10, window_seconds=60)
@require_POST
def resend_otp(request):
    user_id = request.session.get('pending_otp_user')
    purpose = request.session.get('otp_purpose', OTPCode.Purpose.REGISTER)

    if not user_id:
        for key in ('otp_purpose', 'otp_send_succeeded'):
            request.session.pop(key, None)
        messages.info(request, 'Your verification session expired. Please register again.')
        return redirect('register')

    user = User.objects.filter(pk=user_id).first()
    if user is None:
        for key in ('pending_otp_user', 'otp_purpose', 'otp_send_succeeded'):
            request.session.pop(key, None)
        messages.info(request, 'Your verification session expired. Please register again.')
        return redirect('register')

    # Check cooldown and hourly limit
    can_resend, reason = OTPCode.can_resend(user, purpose)
    if not can_resend:
        messages.error(request, reason)
        return redirect('verify_otp')

    _, raw_code = OTPCode.create_otp(
        user=user,
        purpose=purpose,
        channel=OTPCode.Channel.EMAIL,
    )
    try:
        send_succeeded = send_email_otp(user, raw_code, purpose=purpose)
    except Exception as exc:
        log_email_delivery_failure(exc)
        send_succeeded = False

    request.session['otp_send_succeeded'] = bool(send_succeeded)
    if send_succeeded:
        messages.success(request, f'A code was sent to {user.email}.')
    else:
        messages.error(request, VERIFICATION_EMAIL_FAILURE_MESSAGE)

    return redirect('verify_otp')


@ratelimit_view('login', limit=15, window_seconds=60)
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        identifier = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        # Resolve username or email
        user = authenticate(request, username=identifier, password=password)
        if not user and '@' in identifier:
            matched_user = User.objects.filter(email__iexact=identifier).first()
            if matched_user:
                user = authenticate(request, username=matched_user.username, password=password)
        if not user:
            pending_users = User.objects.filter(is_active=False)
            if '@' in identifier:
                pending_users = pending_users.filter(email__iexact=identifier)
            else:
                pending_users = pending_users.filter(username=identifier)
            pending_user = pending_users.first()
            if pending_user and pending_user.check_password(password):
                user = pending_user

        if user is not None:
            # Check if user registered but never verified OTP
            if not user.is_active:
                # Allow them to verify registration
                same_pending_request = (
                    request.session.get('pending_otp_user') == user.pk
                    and request.session.get('otp_purpose') == OTPCode.Purpose.REGISTER
                )
                previous_send_succeeded = (
                    same_pending_request
                    and request.session.get('otp_send_succeeded') is True
                )
                request.session['pending_otp_user'] = user.id
                request.session['otp_purpose'] = OTPCode.Purpose.REGISTER
                request.session['otp_send_succeeded'] = previous_send_succeeded

                can_send, _ = OTPCode.can_resend(user, OTPCode.Purpose.REGISTER)
                if can_send:
                    _, raw_code = OTPCode.create_otp(user, OTPCode.Purpose.REGISTER)
                    try:
                        email_sent = send_email_otp(user, raw_code, purpose='register')
                    except Exception as exc:
                        log_email_delivery_failure(exc)
                        email_sent = False
                    request.session['otp_send_succeeded'] = bool(email_sent)
                else:
                    email_sent = previous_send_succeeded

                if email_sent:
                    messages.info(request, 'Your account is pending verification. Please enter the code sent to your email.')
                else:
                    messages.error(request, EMAIL_SEND_FAILURE_MESSAGE)
                return redirect('verify_otp')

            # User credentials are valid. Check if 2FA login OTP is required.
            login_otp_required = getattr(settings, 'LOGIN_OTP_REQUIRED', True)
            if login_otp_required:
                same_pending_request = (
                    request.session.get('pending_otp_user') == user.pk
                    and request.session.get('otp_purpose') == OTPCode.Purpose.LOGIN
                )
                previous_send_succeeded = (
                    same_pending_request
                    and request.session.get('otp_send_succeeded') is True
                )
                request.session['pending_otp_user'] = user.id
                request.session['otp_purpose'] = OTPCode.Purpose.LOGIN
                request.session['otp_send_succeeded'] = previous_send_succeeded

                can_send, _ = OTPCode.can_resend(user, OTPCode.Purpose.LOGIN)
                if can_send:
                    _, raw_code = OTPCode.create_otp(user, OTPCode.Purpose.LOGIN)
                    try:
                        email_sent = send_email_otp(user, raw_code, purpose='login')
                    except Exception as exc:
                        log_email_delivery_failure(exc)
                        email_sent = False
                    request.session['otp_send_succeeded'] = bool(email_sent)
                else:
                    email_sent = previous_send_succeeded

                if email_sent:
                    messages.info(request, 'A verification code was sent to your email. Enter it below to complete sign in.')
                else:
                    messages.error(request, EMAIL_SEND_FAILURE_MESSAGE)
                return redirect('verify_otp')
            else:
                login(request, user)
                messages.success(request, f'Welcome back, {user.username}!')
                next_url = request.GET.get('next') or 'dashboard'
                return redirect(next_url)
        else:
            messages.error(request, 'Invalid username/email or password.')
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {
        'form': form,
        'email_provider_configured': email_delivery_available(),
    })


@login_required
def profile(request):
    user = request.user

    if user.role == User.Role.CANDIDATE:
        profile_obj, _ = CandidateProfile.objects.get_or_create(user=user)
        form_class = CandidateProfileForm
    elif user.role == User.Role.RECRUITER:
        profile_obj, _ = RecruiterProfile.objects.get_or_create(user=user)
        form_class = RecruiterProfileForm
    else:
        messages.info(request, 'Admins manage settings from the admin panel.')
        return redirect('home')

    if request.method == 'POST':
        form = form_class(request.POST, instance=profile_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
    else:
        form = form_class(instance=profile_obj)

    return render(request, 'accounts/profile.html', {'form': form})


@login_required
def company_verification(request):
    if request.user.role != User.Role.RECRUITER:
        raise PermissionDenied

    profile_obj, _ = RecruiterProfile.objects.get_or_create(user=request.user)
    documents = profile_obj.documents.all().order_by('-uploaded_on')
    has_details = profile_obj.has_required_details()

    if request.method == 'POST':
        if not has_details:
            messages.error(request, 'Complete your company profile before uploading verification documents.')
            return redirect('company_verification')
        if documents.count() >= 3:
            messages.error(request, 'Maximum 3 documents allowed. Please wait for review or contact support.')
            return redirect('company_verification')

        form = RecruiterDocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.cleaned_data['file']
            doc = form.save(commit=False)
            doc.recruiter = profile_obj
            doc.file_name = uploaded_file.name
            doc.content_type = form.cleaned_data.get('validated_content_type', 'application/octet-stream')
            doc.file_size = uploaded_file.size
            doc.file_data = uploaded_file.read()
            doc.status = RecruiterDocument.Status.PENDING
            doc.save()

            messages.success(
                request,
                f'Document "{doc.file_name}" uploaded successfully. Our admin team will review it shortly.',
            )
            return redirect('company_verification')
    else:
        form = RecruiterDocumentUploadForm()

    context = {
        'profile': profile_obj,
        'documents': documents,
        'form': form,
        'can_upload': documents.count() < 3 and has_details,
        'has_details': has_details,
    }
    return render(request, 'accounts/company_verification.html', context)


@login_required
def download_document(request, pk):
    doc = get_object_or_404(RecruiterDocument, pk=pk)

    # Permission check: owner or staff only
    is_owner = (doc.recruiter.user == request.user)
    is_staff = request.user.is_staff or request.user.is_superuser
    if not (is_owner or is_staff):
        raise PermissionDenied

    response = HttpResponse(doc.file_data, content_type=doc.content_type)
    response['Content-Disposition'] = f'attachment; filename="{doc.file_name}"'
    return response
