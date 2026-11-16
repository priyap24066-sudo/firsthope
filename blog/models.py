from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class Article(models.Model):
    class Category(models.TextChoices):
        INTERVIEW_TIPS = 'interview-tips', 'Interview Tips'
        RESUME_TIPS = 'resume-tips', 'Resume Tips'
        SALARY_GUIDE = 'salary-guide', 'Salary Guide'
        CAREER_ADVICE = 'career-advice', 'Career Advice'

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.CAREER_ADVICE)
    excerpt = models.CharField(max_length=300, blank=True, help_text='Short summary shown in listing (max 300 chars)')
    body = models.TextField(help_text='Article content. Use blank lines for paragraphs.')
    published_at = models.DateTimeField(default=timezone.now)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('blog_detail', kwargs={'slug': self.slug})

    def __str__(self):
        return self.title
