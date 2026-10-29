from django.contrib import admin

from .models import Job, JobReport


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('title', 'company_name', 'location', 'recruiter', 'is_active', 'created_at')
    list_filter = ('job_type', 'is_active')
    search_fields = ('title', 'company_name')
    actions = ['deactivate_jobs', 'activate_jobs']

    @admin.action(description='Deactivate selected jobs')
    def deactivate_jobs(self, request, queryset):
        queryset.update(is_active=False)

    @admin.action(description='Activate selected jobs')
    def activate_jobs(self, request, queryset):
        queryset.update(is_active=True)


@admin.register(JobReport)
class JobReportAdmin(admin.ModelAdmin):
    list_display = ('job', 'reported_by', 'reason', 'created_on')
    list_filter = ('created_on',)
    search_fields = ('job__title', 'reported_by__username', 'reason')
