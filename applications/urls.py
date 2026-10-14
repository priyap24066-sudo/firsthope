from django.urls import path

from . import views

urlpatterns = [
    path('mine/', views.my_applications, name='my_applications'),
    path('apply/<int:pk>/', views.apply_job, name='apply_job'),
    path('job/<int:pk>/', views.job_applicants, name='job_applicants'),
    path('<int:pk>/status/', views.update_status, name='update_status'),
    path('<int:pk>/resume/', views.download_resume, name='download_resume'),
]