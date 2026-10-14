from rest_framework.permissions import BasePermission

from accounts.models import User


class IsRecruiter(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.RECRUITER)


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