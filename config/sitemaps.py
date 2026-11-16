"""
Sitemap classes for FirstHope.
Registered at /sitemap.xml in config/urls.py.
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from accounts.models import RecruiterProfile
from blog.models import Article
from jobs.models import Job


class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return ['home', 'job_list', 'blog_list']

    def location(self, item):
        return reverse(item)


class JobSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.9

    def items(self):
        # Only active, verified jobs
        return Job.objects.filter(
            is_active=True,
            recruiter__recruiter_profile__is_verified=True,
        ).select_related('recruiter', 'recruiter__recruiter_profile').order_by('-created_at')

    def lastmod(self, obj):
        return obj.created_at

    def location(self, obj):
        return obj.get_absolute_url()


class CompanySitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return RecruiterProfile.objects.filter(
            is_verified=True,
        ).exclude(company_name='').order_by('company_name')

    def location(self, obj):
        return obj.get_absolute_url()


class BlogSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.7

    def items(self):
        return Article.objects.filter(is_published=True).order_by('-published_at')

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return obj.get_absolute_url()


class CityPageSitemap(Sitemap):
    """
    Generates sitemap entries for /jobs/in-<city>/ programmatic pages.
    Only cities that have at least one active verified job are included.
    """
    changefreq = 'daily'
    priority = 0.7

    def items(self):
        from django.utils.text import slugify
        from django.db.models import Count
        cities = (
            Job.objects.filter(is_active=True, recruiter__recruiter_profile__is_verified=True)
            .values_list('location', flat=True)
            .annotate(count=Count('pk'))
            .order_by()
            .distinct()
        )
        # De-duplicate by slugified name
        seen = set()
        result = []
        for city in cities:
            if city:
                s = slugify(city)
                if s and s not in seen:
                    seen.add(s)
                    result.append(s)
        return result

    def location(self, item):
        return reverse('jobs_in_city', kwargs={'city': item})


class JobTypeSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.6

    def items(self):
        from jobs.models import Job as J
        return [jt.value for jt in J.JobType]

    def location(self, item):
        return reverse('jobs_by_type', kwargs={'job_type': item})
