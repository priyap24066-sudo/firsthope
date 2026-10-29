from django.contrib import admin
from .models import ChatMessage, ChatSession


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'mode', 'created_on')
    list_filter = ('mode', 'created_on')
    search_fields = ('user__username',)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'role', 'content_snippet', 'created_on')
    list_filter = ('role', 'created_on')
    search_fields = ('content', 'session__user__username')

    @admin.display(description='Content')
    def content_snippet(self, obj):
        return obj.content[:50] + ('...' if len(obj.content) > 50 else '')
