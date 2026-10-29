from django.conf import settings
from django.db import models


class ChatSession(models.Model):
    class Mode(models.TextChoices):
        RESUME = 'resume', 'Resume Builder'
        INTERVIEW = 'interview', 'Job Preparation'
        ENGLISH = 'english', 'English Communication'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_sessions',
    )
    mode = models.CharField(max_length=20, choices=Mode.choices, default=Mode.RESUME)
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_on']

    def __str__(self):
        return f"{self.user.username} - {self.get_mode_display()} ({self.created_on.strftime('%Y-%m-%d %H:%M')})"


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = 'user', 'User'
        ASSISTANT = 'assistant', 'Assistant'

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    role = models.CharField(max_length=15, choices=Role.choices)
    content = models.TextField()
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_on']

    def __str__(self):
        return f"{self.role} in session {self.session_id}: {self.content[:30]}"
