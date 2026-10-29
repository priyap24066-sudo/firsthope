from django.urls import path
from . import views

urlpatterns = [
    path('', views.coach_view, name='coach'),
    path('send/', views.coach_send, name='coach_send'),
    path('reset/', views.coach_reset, name='coach_reset'),
]
