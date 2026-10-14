from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import CandidateProfileForm, RecruiterProfileForm, RegisterForm
from .models import CandidateProfile, RecruiterProfile, User


def home(request):
    return render(request, 'home.html')


def register(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully! Welcome to FirstHope.')
            return redirect('home')
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


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
        messages.info(request, 'Admins manage everything from the admin panel.')
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