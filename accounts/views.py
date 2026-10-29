import re
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
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
)
from .otp_sender import is_sms_configured, send_email_otp, send_sms_otp
from .ratelimit import ratelimit_view


from jobs.models import Job


def home(request):
    latest_jobs = Job.objects.filter(
        is_active=True,
        recruiter__recruiter_profile__is_verified=True,
    ).select_related('recruiter', 'recruiter__recruiter_profile')[:6]
    return render(request, 'home.html', {'latest_jobs': latest_jobs})


@ratelimit_view('register', limit=10, window_seconds=60)
def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # Account stays inactive until OTP verification
            user.save()

            # Create & send registration OTP
            otp, raw_code = OTPCode.create_otp(user=user, purpose=OTPCode.Purpose.REGISTER)
            send_email_otp(user, raw_code, purpose='register')

            request.session['pending_otp_user'] = user.id
            request.session['otp_purpose'] = OTPCode.Purpose.REGISTER
            request.session['otp_channel'] = 'email'

            messages.success(
                request,
                f'Account created! We have sent a 6-digit verification code to {user.email}. Please verify below.',
            )
            return redirect('verify_otp')
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


@ratelimit_view('verify_otp', limit=15, window_seconds=60)
def verify_otp(request):
    user_id = request.session.get('pending_otp_user')
    purpose = request.session.get('otp_purpose', OTPCode.Purpose.REGISTER)

    if not user_id:
        messages.info(request, 'No verification session in progress. Please log in or register.')
        return redirect('login')

    user = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        form = VerifyOTPForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            active_otp = OTPCode.objects.filter(
                user=user,
                purpose=purpose,
                is_used=False,
            ).first()

            if not active_otp:
                messages.error(request, 'No active OTP found. Please request a new code.')
            else:
                success, msg = active_otp.verify(code)
                if success:
                    # Clear session keys
                    request.session.pop('pending_otp_user', None)
                    request.session.pop('otp_purpose', None)
                    request.session.pop('otp_channel', None)

                    if purpose == OTPCode.Purpose.REGISTER:
                        user.is_active = True
                        user.save(update_fields=['is_active'])
                        login(request, user)
                        messages.success(request, 'Email verified successfully! Welcome to FirstHope.')
                        return redirect('dashboard')
                    else:
                        login(request, user)
                        messages.success(request, 'Verification successful.')
                        next_url = request.GET.get('next') or 'dashboard'
                        return redirect(next_url)
                else:
                    messages.error(request, msg)
    else:
        form = VerifyOTPForm()

    channel = request.session.get('otp_channel', 'email')
    masked_target = user.email
    if channel == 'sms' and user.phone:
        masked_target = f"+91 ******{user.phone[-4:]}"

    context = {
        'form': form,
        'user_obj': user,
        'purpose': purpose,
        'channel': channel,
        'target': masked_target,
        'sms_available': is_sms_configured() and bool(user.phone),
    }
    return render(request, 'accounts/verify_otp.html', context)


@ratelimit_view('resend_otp', limit=10, window_seconds=60)
def resend_otp(request):
    user_id = request.session.get('pending_otp_user')
    purpose = request.session.get('otp_purpose', OTPCode.Purpose.REGISTER)

    if not user_id:
        messages.error(request, 'Session expired. Please sign in or register again.')
        return redirect('login')

    user = get_object_or_404(User, pk=user_id)

    # Check cooldown and hourly limit
    can_resend, reason = OTPCode.can_resend(user, purpose)
    if not can_resend:
        messages.error(request, reason)
        return redirect('verify_otp')

    # Desired channel
    channel = request.GET.get('channel', request.session.get('otp_channel', 'email'))
    if channel == 'sms' and not (is_sms_configured() and user.phone):
        channel = 'email'

    request.session['otp_channel'] = channel

    otp_channel = OTPCode.Channel.SMS if channel == 'sms' else OTPCode.Channel.EMAIL
    otp, raw_code = OTPCode.create_otp(user=user, purpose=purpose, channel=otp_channel)

    if channel == 'sms':
        send_sms_otp(user, raw_code, purpose=purpose)
        messages.success(request, f'A new verification code was sent to your phone (+91 ******{user.phone[-4:]}).')
    else:
        send_email_otp(user, raw_code, purpose=purpose)
        messages.success(request, f'A new verification code was sent to {user.email}.')

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

        if user is not None:
            # Check if user registered but never verified OTP
            if not user.is_active:
                # Allow them to verify registration
                request.session['pending_otp_user'] = user.id
                request.session['otp_purpose'] = OTPCode.Purpose.REGISTER
                request.session['otp_channel'] = 'email'

                can_send, _ = OTPCode.can_resend(user, OTPCode.Purpose.REGISTER)
                if can_send:
                    _, raw_code = OTPCode.create_otp(user, OTPCode.Purpose.REGISTER)
                    send_email_otp(user, raw_code, purpose='register')

                messages.info(request, 'Your account is pending verification. Please enter the OTP sent to your email.')
                return redirect('verify_otp')

            # User credentials are valid. Check if 2FA login OTP is required.
            login_otp_required = getattr(settings, 'LOGIN_OTP_REQUIRED', True)
            if login_otp_required:
                request.session['pending_otp_user'] = user.id
                request.session['otp_purpose'] = OTPCode.Purpose.LOGIN
                request.session['otp_channel'] = 'email'

                can_send, _ = OTPCode.can_resend(user, OTPCode.Purpose.LOGIN)
                if can_send:
                    _, raw_code = OTPCode.create_otp(user, OTPCode.Purpose.LOGIN)
                    send_email_otp(user, raw_code, purpose='login')

                messages.info(request, f'Verification code sent to {user.email}. Enter it below to complete sign in.')
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

    return render(request, 'accounts/login.html', {'form': form})


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

    if request.method == 'POST':
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

    has_details = profile_obj.has_required_details()

    context = {
        'profile': profile_obj,
        'documents': documents,
        'form': form,
        'can_upload': documents.count() < 3,
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
