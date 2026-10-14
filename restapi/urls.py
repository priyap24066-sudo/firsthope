from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('jobs', views.JobViewSet, basename='api-job')
router.register('applications', views.ApplicationViewSet, basename='api-application')
router.register('interviews', views.InterviewViewSet, basename='api-interview')

urlpatterns = [
    path('me/', views.MeView.as_view(), name='api-me'),
    path('', include(router.urls)),
]