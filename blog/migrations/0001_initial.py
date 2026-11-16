"""
Migration: create blog Article model.
"""
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Article',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('slug', models.SlugField(blank=True, max_length=220, unique=True)),
                ('category', models.CharField(
                    choices=[
                        ('interview-tips', 'Interview Tips'),
                        ('resume-tips', 'Resume Tips'),
                        ('salary-guide', 'Salary Guide'),
                        ('career-advice', 'Career Advice'),
                    ],
                    default='career-advice',
                    max_length=30,
                )),
                ('excerpt', models.CharField(blank=True, help_text='Short summary shown in listing (max 300 chars)', max_length=300)),
                ('body', models.TextField(help_text='Article content. Use blank lines for paragraphs.')),
                ('published_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('is_published', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-published_at'],
            },
        ),
    ]
