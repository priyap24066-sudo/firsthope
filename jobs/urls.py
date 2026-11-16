from django.urls import path

from . import views

urlpatterns = [
    # Job listing & search
    path('', views.job_list, name='job_list'),

    # Recruiter management
    path('my/', views.my_jobs, name='my_jobs'),
    path('post/', views.job_create, name='job_create'),

    # Saved jobs (candidate)
    path('saved/', views.saved_jobs, name='saved_jobs'),
    path('<int:pk>/save/', views.toggle_save_job, name='toggle_save_job'),

    # Job alerts
    path('alerts/', views.job_alerts, name='job_alerts'),
    path('alerts/<int:pk>/delete/', views.delete_job_alert, name='delete_job_alert'),

    # SEO-friendly slug URL (primary)
    path('<slug:slug>-<int:pk>/', views.job_detail, name='job_detail'),

    # 301 redirect: old /jobs/<pk>/ → new slug URL
    path('<int:pk>/', views.job_detail_redirect, name='job_detail_legacy'),

    # Recruiter actions (use pk-only for internal admin links)
    path('<int:pk>/edit/', views.job_edit, name='job_edit'),
    path('<int:pk>/delete/', views.job_delete, name='job_delete'),
    path('<int:pk>/report/', views.report_job, name='report_job'),

    # Programmatic landing pages
    path('in-<slug:city>/', views.jobs_in_city, name='jobs_in_city'),
    path('type/<slug:job_type>/', views.jobs_by_type, name='jobs_by_type'),
]
