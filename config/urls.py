from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path('manifest.json', TemplateView.as_view(
        template_name='pwa/manifest.json',
        content_type='application/manifest+json')),
    path('sw.js', TemplateView.as_view(
        template_name='pwa/sw.js',
        content_type='application/javascript')),
    path('admin/', admin.site.urls),
    path('api/', include('restapi.urls')),
    path('api-auth/', include('rest_framework.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('jobs/', include('jobs.urls')),
    path('applications/', include('applications.urls')),
    path('interviews/', include('interviews.urls')),
    path('', include('accounts.urls')),
]