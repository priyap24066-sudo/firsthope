from django.contrib import admin
from .models import Article

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'published_at', 'is_published')
    list_filter = ('category', 'is_published')
    search_fields = ('title', 'body')
    prepopulated_fields = {'slug': ('title',)}
    ordering = ('-published_at',)
