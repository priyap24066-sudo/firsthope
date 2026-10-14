from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from applications.models import Application
from interviews.models import Interview
from jobs.models import Job

from .permissions import IsCandidate, IsRecruiter, IsRecruiterOrCandidate
from .serializers import ApplicationSerializer, InterviewSerializer, JobSerializer


class JobViewSet(viewsets.ModelViewSet):
    serializer_class = JobSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [AllowAny()]
        return [IsRecruiter()]

    def get_queryset(self):
        user = self.request.user
        queryset = Job.objects.select_related('recruiter')

        # edit / delete: only own jobs
        if self.action in ('update', 'partial_update', 'destroy'):
            return queryset.filter(recruiter=user)

        # read: active jobs (recruiter also sees own closed jobs)
        if user.is_authenticated and user.role == User.Role.RECRUITER:
            queryset = queryset.filter(Q(is_active=True) | Q(recruiter=user))
        else:
            queryset = queryset.filter(is_active=True)

        if self.action == 'list':
            params = self.request.query_params
            q = params.get('q', '').strip()
            location = params.get('location', '').strip()
            job_type = params.get('job_type', '').strip()
            if q:
                queryset = queryset.filter(
                    Q(title__icontains=q)
                    | Q(company_name__icontains=q)
                    | Q(skills_required__icontains=q)
                )
            if location:
                queryset = queryset.filter(location__icontains=location)
            if job_type:
                queryset = queryset.filter(job_type=job_type)
        return queryset

    def perform_create(self, serializer):
        serializer.save(recruiter=self.request.user)


class ApplicationViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ApplicationSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [IsCandidate()]
        if self.action == 'set_status':
            return [IsRecruiter()]
        return [IsRecruiterOrCandidate()]

    def get_queryset(self):
        user = self.request.user
        queryset = Application.objects.select_related('job', 'candidate')
        if user.role == User.Role.CANDIDATE:
            return queryset.filter(candidate=user)
        if user.role == User.Role.RECRUITER:
            return queryset.filter(job__recruiter=user)
        return queryset.none()

    def perform_create(self, serializer):
        serializer.save(candidate=self.request.user)

    @action(detail=True, methods=['patch'], url_path='status')
    def set_status(self, request, pk=None):
        application = self.get_object()     # only own job's applications
        new_status = request.data.get('status')
        valid_statuses = [value for value, _ in Application.Status.choices]

        if new_status not in valid_statuses:
            return Response(
                {'status': [f'Invalid status. Choose from: {", ".join(valid_statuses)}']},
                status=400,
            )
        application.status = new_status
        application.save(update_fields=['status'])
        return Response(self.get_serializer(application).data)


class InterviewViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InterviewSerializer
    permission_classes = [IsRecruiterOrCandidate]

    def get_queryset(self):
        user = self.request.user
        queryset = Interview.objects.select_related(
            'application__job', 'application__candidate'
        )
        if user.role == User.Role.CANDIDATE:
            return queryset.filter(application__candidate=user)
        if user.role == User.Role.RECRUITER:
            return queryset.filter(application__job__recruiter=user)
        return queryset.none()


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
        }
        if user.role == User.Role.CANDIDATE and hasattr(user, 'candidate_profile'):
            p = user.candidate_profile
            data['profile'] = {
                'phone': p.phone,
                'location': p.location,
                'skills': p.skills,
                'experience_years': p.experience_years,
                'education': p.education,
            }
        elif user.role == User.Role.RECRUITER and hasattr(user, 'recruiter_profile'):
            p = user.recruiter_profile
            data['profile'] = {
                'company_name': p.company_name,
                'company_website': p.company_website,
                'location': p.location,
                'designation': p.designation,
            }
        return Response(data)