from rest_framework.permissions import BasePermission

from accounts.models import User


class IsRecruiter(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.RECRUITER)


class IsVerifiedRecruiter(BasePermission):
    message = "Your company is pending verification by the admin."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.role == User.Role.RECRUITER):
            return False
        profile = getattr(user, 'recruiter_profile', None)
        return bool(profile and profile.is_verified)


class IsCandidate(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.CANDIDATE)


class IsRecruiterOrCandidate(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.role in (User.Role.RECRUITER, User.Role.CANDIDATE)
        )
