import json
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from .ai_client import generate_chat_reply
from .models import ChatMessage, ChatSession


def candidate_check(user):
    return user.is_authenticated and user.role == User.Role.CANDIDATE


def get_daily_usage(user):
    today = timezone.localdate()
    return ChatMessage.objects.filter(
        session__user=user,
        role=ChatMessage.Role.USER,
        created_on__date=today,
    ).count()


@login_required
def coach_view(request):
    if request.user.role == User.Role.RECRUITER:
        return render(
            request,
            'chatbot/coach_recruiter_blocked.html',
            {'message': 'The AI Coach is exclusively designed for job candidates to practice interviews, build resumes, and improve communication.'},
            status=403,
        )
    if request.user.role != User.Role.CANDIDATE:
        raise PermissionDenied

    mode = request.GET.get('mode', 'resume').lower()
    if mode not in ('resume', 'interview', 'english'):
        mode = 'resume'

    # Get or create active session for this mode
    session, _ = ChatSession.objects.get_or_create(user=request.user, mode=mode)
    messages = session.messages.all().order_by('created_on')

    limit = getattr(settings, 'AI_DAILY_LIMIT', 30)
    used = get_daily_usage(request.user)
    remaining = max(0, limit - used)

    context = {
        'mode': mode,
        'session': session,
        'chat_messages': messages,
        'remaining_messages': remaining,
        'daily_limit': limit,
    }
    return render(request, 'chatbot/coach.html', context)


@login_required
@require_POST
def coach_send(request):
    if request.user.role != User.Role.CANDIDATE:
        return JsonResponse({'success': False, 'error': 'Only candidates can access AI Coach.'}, status=403)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST

    mode = data.get('mode', 'resume').lower()
    if mode not in ('resume', 'interview', 'english'):
        mode = 'resume'

    user_message = data.get('message', '').strip()
    if not user_message:
        return JsonResponse({'success': False, 'error': 'Please enter a message.'}, status=400)

    if len(user_message) > 500:
        return JsonResponse(
            {'success': False, 'error': f'Message exceeds maximum limit of 500 characters ({len(user_message)} characters entered).'},
            status=400,
        )

    limit = getattr(settings, 'AI_DAILY_LIMIT', 30)
    used = get_daily_usage(request.user)
    if used >= limit:
        return JsonResponse(
            {'success': False, 'error': f'You have reached your daily limit of {limit} messages. Please return tomorrow.'},
            status=429,
        )

    # Get session
    session, _ = ChatSession.objects.get_or_create(user=request.user, mode=mode)

    # Save user message
    user_msg_obj = ChatMessage.objects.create(
        session=session,
        role=ChatMessage.Role.USER,
        content=user_message,
    )

    # History prior to this message
    history = session.messages.exclude(pk=user_msg_obj.pk).order_by('created_on')

    # Generate reply
    success, reply_text = generate_chat_reply(mode, user_message, history, user=request.user)

    # Save assistant message
    ChatMessage.objects.create(
        session=session,
        role=ChatMessage.Role.ASSISTANT,
        content=reply_text,
    )

    new_remaining = max(0, limit - (used + 1))

    return JsonResponse({
        'success': success,
        'reply': reply_text,
        'remaining': new_remaining,
    })


@login_required
@require_POST
def coach_reset(request):
    if request.user.role != User.Role.CANDIDATE:
        raise PermissionDenied
    mode = request.POST.get('mode', 'resume').lower()
    # Delete old sessions for this mode or create a fresh one
    ChatSession.objects.filter(user=request.user, mode=mode).delete()
    ChatSession.objects.create(user=request.user, mode=mode)
    return redirect(f"/coach/?mode={mode}")
