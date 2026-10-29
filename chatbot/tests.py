from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User

from . import ai_client
from .models import ChatMessage, ChatSession


class AIClientTests(TestCase):
    @override_settings(GEMINI_API_KEY='')
    @patch.dict('os.environ', {'GEMINI_API_KEY': ''})
    @patch('chatbot.ai_client.get_ai_client')
    def test_missing_api_key_returns_configuration_message(self, get_client):
        success, reply = ai_client.generate_chat_reply('resume', 'Hello', [])

        self.assertFalse(success)
        self.assertEqual(
            reply,
            'AI Coach is not configured. Please set the GEMINI_API_KEY environment variable.',
        )
        get_client.assert_not_called()

    @override_settings(GEMINI_API_KEY='test-key', AI_MODEL='gemini-test')
    @patch.dict('os.environ', {'AI_MODEL': 'gemini-test'})
    @patch('chatbot.ai_client.get_ai_client')
    def test_gemini_request_uses_safe_context_and_generation_limits(self, get_client):
        client = Mock()
        client.models.generate_content.return_value = SimpleNamespace(text='  Gemini reply  ')
        get_client.return_value = client
        history = [
            SimpleNamespace(role='user', content='Earlier question'),
            SimpleNamespace(role='assistant', content='Earlier reply'),
        ]
        user = SimpleNamespace(
            email='private@example.com',
            phone='9876543210',
            candidate_profile=SimpleNamespace(
                education='BSc Computer Science',
                skills='Python, Django',
                experience_years=2,
                about='Private profile details',
            ),
        )

        success, reply = ai_client.generate_chat_reply(
            'resume', 'Current question', history, user=user,
        )

        self.assertTrue(success)
        self.assertEqual(reply, 'Gemini reply')
        kwargs = client.models.generate_content.call_args.kwargs
        self.assertEqual(kwargs['model'], 'gemini-test')
        self.assertEqual(kwargs['contents'], [
            {'role': 'user', 'parts': [{'text': 'Earlier question'}]},
            {'role': 'model', 'parts': [{'text': 'Earlier reply'}]},
            {'role': 'user', 'parts': [{'text': 'Current question'}]},
        ])
        self.assertEqual(kwargs['config']['max_output_tokens'], 700)
        system_instruction = kwargs['config']['system_instruction']
        self.assertIn('BSc Computer Science', system_instruction)
        self.assertIn('Python, Django', system_instruction)
        self.assertIn('2 years', system_instruction)
        self.assertNotIn(user.email, system_instruction)
        self.assertNotIn(user.phone, system_instruction)
        self.assertNotIn('Private profile details', system_instruction)

    @override_settings(GEMINI_API_KEY='test-key')
    @patch('chatbot.ai_client.get_ai_client')
    def test_rate_limit_returns_retry_message_without_exception_details(self, get_client):
        class RateLimitError(Exception):
            code = 429

        client = Mock()
        client.models.generate_content.side_effect = RateLimitError('private SDK details')
        get_client.return_value = client

        success, reply = ai_client.generate_chat_reply('english', 'Hello', [])

        self.assertFalse(success)
        self.assertEqual(reply, 'AI Coach is busy, please try again in a minute.')
        self.assertNotIn('private SDK details', reply)


class CoachSendTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='coach_candidate',
            email='coach_candidate@example.com',
            password='StrongPass123!',
            role=User.Role.CANDIDATE,
        )
        self.client.force_login(self.user)
        self.url = reverse('coach_send')

    @patch('chatbot.views.generate_chat_reply', return_value=(True, 'Mocked reply'))
    def test_send_uses_mocked_ai_and_returns_reply(self, generate_reply):
        response = self.client.post(
            self.url,
            data={'mode': 'resume', 'message': 'Help me with my resume'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['reply'], 'Mocked reply')
        generate_reply.assert_called_once()
        self.assertEqual(
            ChatMessage.objects.filter(session__user=self.user).count(),
            2,
        )

    @patch('chatbot.views.generate_chat_reply')
    def test_send_rejects_messages_over_500_characters(self, generate_reply):
        response = self.client.post(
            self.url,
            data={'mode': 'resume', 'message': 'x' * 501},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        generate_reply.assert_not_called()

    @override_settings(AI_DAILY_LIMIT=1)
    @patch('chatbot.views.generate_chat_reply')
    def test_send_enforces_daily_limit(self, generate_reply):
        session = ChatSession.objects.create(user=self.user, mode='resume')
        ChatMessage.objects.create(
            session=session,
            role=ChatMessage.Role.USER,
            content='Already sent today',
        )

        response = self.client.post(
            self.url,
            data={'mode': 'resume', 'message': 'One more message'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 429)
        generate_reply.assert_not_called()
