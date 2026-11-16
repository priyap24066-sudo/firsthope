"""
Migration: add slug, expires_at, SavedJob, JobAlert to jobs app.
Backfills slug for all existing Job rows using slugify(title).
Also adds DB indexes on is_active, location, job_type, slug.
"""
from django.conf import settings
from django.db import migrations, models
from django.utils.text import slugify
import django.db.models.deletion


def backfill_slugs(apps, schema_editor):
    Job = apps.get_model('jobs', 'Job')
    for job in Job.objects.all():
        if not job.slug:
            job.slug = slugify(job.title) or f'job-{job.pk}'
            job.save(update_fields=['slug'])


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Add slug field (allow blank during migration)
        migrations.AddField(
            model_name='job',
            name='slug',
            field=models.SlugField(blank=True, max_length=180),
        ),
        # 2. Add expires_at field
        migrations.AddField(
            model_name='job',
            name='expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        # 3. Backfill slugs for existing rows
        migrations.RunPython(backfill_slugs, migrations.RunPython.noop),
        # 4. Add indexes
        migrations.AddIndex(
            model_name='job',
            index=models.Index(fields=['is_active'], name='jobs_job_is_active_idx'),
        ),
        migrations.AddIndex(
            model_name='job',
            index=models.Index(fields=['is_active', '-created_at'], name='jobs_job_active_created_idx'),
        ),
        migrations.AddIndex(
            model_name='job',
            index=models.Index(fields=['location'], name='jobs_job_location_idx'),
        ),
        migrations.AddIndex(
            model_name='job',
            index=models.Index(fields=['job_type'], name='jobs_job_type_idx'),
        ),
        migrations.AddIndex(
            model_name='job',
            index=models.Index(fields=['slug'], name='jobs_job_slug_idx'),
        ),
        # 5. Create SavedJob model
        migrations.CreateModel(
            name='SavedJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('saved_at', models.DateTimeField(auto_now_add=True)),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='saves', to='jobs.job')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='saved_jobs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-saved_at'],
                'unique_together': {('user', 'job')},
            },
        ),
        # 6. Create JobAlert model
        migrations.CreateModel(
            name='JobAlert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('keyword', models.CharField(blank=True, help_text='Job title, skill, or company keyword', max_length=100)),
                ('location', models.CharField(blank=True, help_text='City or region', max_length=100)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='job_alerts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
