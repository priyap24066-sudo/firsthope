from django.shortcuts import get_object_or_404, render

from .models import Article


def blog_list(request):
    articles = Article.objects.filter(is_published=True)
    category = request.GET.get('category', '').strip()
    if category:
        articles = articles.filter(category=category)
    return render(request, 'blog/blog_list.html', {
        'articles': articles,
        'category': category,
        'categories': Article.Category.choices,
    })


def blog_detail(request, slug):
    article = get_object_or_404(Article, slug=slug, is_published=True)
    related = Article.objects.filter(
        is_published=True,
        category=article.category,
    ).exclude(pk=article.pk)[:3]
    return render(request, 'blog/blog_detail.html', {
        'article': article,
        'related': related,
    })
