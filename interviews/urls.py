from django.urls import path

from . import views

urlpatterns = [
    path('schedule/<int:application_id>/', views.schedule_interview, name='schedule_interview'),
    path('manage/', views.recruiter_interviews, name='recruiter_interviews'),
    path('<int:pk>/status/', views.update_interview_status, name='update_interview_status'),
    path('mine/', views.my_interviews, name='my_interviews'),
]