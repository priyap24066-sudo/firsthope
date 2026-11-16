"""
Migration: add company_slug to RecruiterProfile and backfill from company_name.
"""
from django.db import migrations, models
from django.utils.text import slugify


def backfill_company_slugs(apps, schema_editor):
    RecruiterProfile = apps.get_model('accounts', 'RecruiterProfile')
    seen = {}
    for profile in RecruiterProfile.objects.exclude(company_name='').order_by('id'):
        base = slugify(profile.company_name) or f'company-{profile.pk}'
        slug = base
        counter = 1
        while slug in seen:
            slug = f'{base}-{counter}'
            counter += 1
        seen[slug] = True
        profile.company_slug = slug
        profile.save(update_fields=['company_slug'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_remove_sms_otp_channel'),
    ]

    operations = [
        migrations.AddField(
            model_name='recruiterprofile',
            name='company_slug',
            field=models.SlugField(blank=True, max_length=180, db_index=True),
        ),
        migrations.RunPython(backfill_company_slugs, migrations.RunPython.noop),
    ]
