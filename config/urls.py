from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import include, path
from django.views.generic import TemplateView

from config.sitemaps import (
    BlogSitemap,
    CityPageSitemap,
    CompanySitemap,
    JobSitemap,
    JobTypeSitemap,
    StaticViewSitemap,
)

sitemaps = {
    'static': StaticViewSitemap,
    'jobs': JobSitemap,
    'companies': CompanySitemap,
    'blog': BlogSitemap,
    'cities': CityPageSitemap,
    'job_types': JobTypeSitemap,
}


def health_check(request):
    """Simple uptime/health endpoint — keeps Render from cold-starting."""
    return HttpResponse('ok', content_type='text/plain')


def robots_txt(request):
    return render(request, 'robots.txt', content_type='text/plain')


urlpatterns = [
    # PWA
    path('manifest.json', TemplateView.as_view(
        template_name='pwa/manifest.json',
        content_type='application/manifest+json')),
    path('sw.js', TemplateView.as_view(
        template_name='pwa/sw.js',
        content_type='application/javascript')),

    # Health & SEO utility endpoints
    path('health/', health_check, name='health'),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),

    # Admin
    path('admin/', admin.site.urls),

    # API
    path('api/', include('restapi.urls')),
    path('api-auth/', include('rest_framework.urls')),

    # Feature apps
    path('dashboard/', include('dashboard.urls')),
    path('jobs/', include('jobs.urls')),
    path('applications/', include('applications.urls')),
    path('interviews/', include('interviews.urls')),
    path('coach/', include('chatbot.urls')),
    path('blog/', include('blog.urls')),

    # Accounts + home (must be last — catches '/')
    path('', include('accounts.urls')),
]
