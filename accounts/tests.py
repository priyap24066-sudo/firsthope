import os
import runpy
from contextlib import redirect_stdout
from datetime import timedelta
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.admin.sites import AdminSite
from django.contrib import messages
from django.core.cache import cache
from django.core import mail
from django.core.mail.backends.base import BaseEmailBackend
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .admin import RecruiterDocumentAdmin, RecruiterProfileAdmin, check_recruiter_domain_match
from .email_delivery import (
    ADMIN_EMAIL_WARNING,
    EMAIL_SEND_FAILURE_MESSAGE,
    email_delivery_available,
)
from .models import CandidateProfile, OTPCode, RecruiterDocument, RecruiterProfile, User
from .otp_sender import send_email_otp

PASSWORD = 'Str0ng!Pass#2026'


class FailingEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        raise RuntimeError('OTP 654321 API key test-secret')


class EmailConfigurationTests(TestCase):
    settings_path = Path(__file__).resolve().parents[1] / 'config' / 'settings.py'

    def load_settings(self, environment):
        with patch.dict(os.environ, environment):
            return runpy.run_path(str(self.settings_path))

    def test_brevo_backend_is_used_when_api_key_is_set(self):
        configured = self.load_settings({
            'BREVO_API_KEY': 'test-brevo-key',
            'EMAIL_HOST': 'smtp.example.com',
            'DEFAULT_FROM_EMAIL': 'FirstHope <verified@example.com>',
        })

        self.assertEqual(configured['EMAIL_BACKEND'], 'accounts.email_delivery.FailSafeEmailBackend')
        self.assertEqual(configured['EMAIL_TRANSPORT_BACKEND'], 'anymail.backends.brevo.EmailBackend')
        self.assertEqual(configured['ANYMAIL'], {'BREVO_API_KEY': 'test-brevo-key'})
        self.assertIn('anymail', configured['INSTALLED_APPS'])
        self.assertEqual(configured['DEFAULT_FROM_EMAIL'], 'FirstHope <verified@example.com>')

    def test_console_backend_remains_default_without_email_host_or_brevo_key(self):
        configured = self.load_settings({'DEBUG': 'True', 'BREVO_API_KEY': '', 'EMAIL_HOST': ''})

        self.assertEqual(configured['EMAIL_BACKEND'], 'accounts.email_delivery.FailSafeEmailBackend')
        self.assertEqual(
            configured['EMAIL_TRANSPORT_BACKEND'],
            'django.core.mail.backends.console.EmailBackend',
        )

    def test_gmail_backend_is_used_when_all_credentials_are_set(self):
        configured = self.load_settings({
            'GMAIL_API_CLIENT_ID': 'client-id',
            'GMAIL_API_CLIENT_SECRET': 'client-secret',
            'GMAIL_API_REFRESH_TOKEN': 'refresh-token',
            'BREVO_API_KEY': '',
            'EMAIL_HOST': '',
        })

        self.assertEqual(configured['EMAIL_BACKEND'], 'gmailapi_backend.mail.GmailBackend')
        self.assertEqual(configured['GMAIL_API_CLIENT_ID'], 'client-id')
        self.assertEqual(configured['GMAIL_API_CLIENT_SECRET'], 'client-secret')
        self.assertEqual(configured['GMAIL_API_REFRESH_TOKEN'], 'refresh-token')
        self.assertTrue(configured['EMAIL_PROVIDER_CONFIGURED'])
        self.assertIn('gmailapi_backend', configured['INSTALLED_APPS'])

    def test_partial_gmail_credentials_keep_existing_backend_behavior(self):
        configured = self.load_settings({
            'GMAIL_API_CLIENT_ID': 'client-id',
            'GMAIL_API_CLIENT_SECRET': '',
            'GMAIL_API_REFRESH_TOKEN': 'refresh-token',
            'BREVO_API_KEY': '',
            'EMAIL_HOST': '',
            'DEBUG': 'True',
        })

        self.assertEqual(
            configured['EMAIL_BACKEND'],
            'accounts.email_delivery.FailSafeEmailBackend',
        )
        self.assertEqual(
            configured['EMAIL_TRANSPORT_BACKEND'],
            'django.core.mail.backends.console.EmailBackend',
        )
        self.assertFalse(configured['GMAIL_API_CONFIGURED'])

    @override_settings(
        EMAIL_PROVIDER_CONFIGURED=False,
        EMAIL_BACKEND='gmailapi_backend.mail.GmailBackend',
    )
    def test_gmail_backend_is_reported_as_available(self):
        self.assertTrue(email_delivery_available())

    def test_dummy_backend_is_used_without_provider_in_production(self):
        with patch.dict(
            os.environ,
            {'DEBUG': 'False', 'BREVO_API_KEY': '', 'EMAIL_HOST': ''},
            clear=True,
        ):
            configured = runpy.run_path(str(self.settings_path))

        self.assertFalse(configured['EMAIL_PROVIDER_CONFIGURED'])
        self.assertEqual(
            configured['EMAIL_BACKEND'],
            'django.core.mail.backends.dummy.EmailBackend',
        )
        self.assertEqual(
            configured['EMAIL_TRANSPORT_BACKEND'],
            'django.core.mail.backends.dummy.EmailBackend',
        )

    def test_smtp_backend_remains_available_without_brevo_key(self):
        configured = self.load_settings({'BREVO_API_KEY': '', 'EMAIL_HOST': 'smtp.example.com'})

        self.assertEqual(
            configured['EMAIL_TRANSPORT_BACKEND'],
            'django.core.mail.backends.smtp.EmailBackend',
        )

    def test_registration_otp_is_required_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            configured = runpy.run_path(str(self.settings_path))

        self.assertTrue(configured['REGISTER_OTP_REQUIRED'])

    def test_registration_otp_setting_reads_environment(self):
        for value, expected in (('True', True), ('False', False)):
            with self.subTest(value=value):
                configured = self.load_settings({'REGISTER_OTP_REQUIRED': value})
                self.assertIs(configured['REGISTER_OTP_REQUIRED'], expected)


class EmailDeliveryTests(TestCase):
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_otp_is_sent_through_django_email_framework(self):
        user = User(username='email_user', email='email@example.com')

        self.assertTrue(send_email_otp(user, '123456', purpose='register'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('123456', mail.outbox[0].body)

    def test_failed_delivery_logs_only_exception_type(self):
        with patch(
            'accounts.email_delivery.send_mail',
            side_effect=RuntimeError('OTP 123456 API key secret-value'),
        ):
            with self.assertLogs('accounts.email_delivery', level='ERROR') as captured:
                sent = send_email_otp(
                    User(username='email_user', email='email@example.com'),
                    '123456',
                    purpose='register',
                )

        self.assertFalse(sent)
        self.assertEqual(captured.output, ['ERROR:accounts.email_delivery:Email delivery failed (RuntimeError)'])
        self.assertNotIn('123456', captured.output[0])
        self.assertNotIn('secret-value', captured.output[0])

    @override_settings(
        EMAIL_BACKEND='accounts.email_delivery.FailSafeEmailBackend',
        EMAIL_TRANSPORT_BACKEND='accounts.tests.FailingEmailBackend',
    )
    def test_backend_failure_does_not_log_otp_or_email_content(self):
        with self.assertLogs('accounts.email_delivery', level='ERROR') as captured:
            sent = send_email_otp(
                User(username='email_user', email='email@example.com'),
                '654321',
                purpose='register',
            )

        self.assertFalse(sent)
        self.assertEqual(captured.output, ['ERROR:accounts.email_delivery:Email delivery failed (RuntimeError)'])
        self.assertNotIn('654321', captured.output[0])
        self.assertNotIn('API key', captured.output[0])
        self.assertNotIn('test-secret', captured.output[0])

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.dummy.EmailBackend')
    def test_dummy_backend_does_not_print_or_log_otp(self):
        output = StringIO()
        with redirect_stdout(output):
            with self.assertNoLogs('accounts.email_delivery', level='ERROR'):
                sent = send_email_otp(
                    User(username='email_user', email='email@example.com'),
                    '654321',
                    purpose='register',
                )

        self.assertTrue(sent)
        self.assertNotIn('654321', output.getvalue())


class EmailFailureSafetyTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='email_admin',
            email='admin@example.com',
            password=PASSWORD,
        )
        self.recruiter = User.objects.create_user(
            username='email_recruiter',
            email='recruiter@example.com',
            password=PASSWORD,
            role=User.Role.RECRUITER,
        )
        self.document = RecruiterDocument.objects.create(
            recruiter=self.recruiter.recruiter_profile,
            document_type=RecruiterDocument.DocType.REGISTRATION,
            file_name='registration.pdf',
            content_type='application/pdf',
            file_data=b'%PDF-1.4 test document',
            file_size=23,
        )

    @override_settings(
        EMAIL_BACKEND='accounts.email_delivery.FailSafeEmailBackend',
        EMAIL_TRANSPORT_BACKEND='accounts.tests.FailingEmailBackend',
    )
    def test_admin_approval_is_saved_and_warns_when_email_fails(self):
        document_admin = RecruiterDocumentAdmin(RecruiterDocument, AdminSite())
        document_admin.message_user = Mock()
        request = SimpleNamespace(user=self.admin_user)

        with self.assertLogs('accounts.email_delivery', level='ERROR') as captured:
            document_admin.approve_documents(
                request,
                RecruiterDocument.objects.filter(pk=self.document.pk),
            )

        self.document.refresh_from_db()
        self.recruiter.recruiter_profile.refresh_from_db()
        self.assertEqual(self.document.status, RecruiterDocument.Status.APPROVED)
        self.assertTrue(self.recruiter.recruiter_profile.is_verified)
        document_admin.message_user.assert_called_once_with(
            request,
            ADMIN_EMAIL_WARNING,
            level=messages.WARNING,
        )
        self.assertEqual(captured.output, ['ERROR:accounts.email_delivery:Email delivery failed (RuntimeError)'])

    @override_settings(
        EMAIL_BACKEND='accounts.email_delivery.FailSafeEmailBackend',
        EMAIL_TRANSPORT_BACKEND='accounts.tests.FailingEmailBackend',
    )
    def test_admin_rejection_is_saved_and_warns_when_email_fails(self):
        document_admin = RecruiterDocumentAdmin(RecruiterDocument, AdminSite())
        document_admin.message_user = Mock()
        request = SimpleNamespace(user=self.admin_user)

        with self.assertLogs('accounts.email_delivery', level='ERROR') as captured:
            document_admin.reject_documents(
                request,
                RecruiterDocument.objects.filter(pk=self.document.pk),
            )

        self.document.refresh_from_db()
        self.assertEqual(self.document.status, RecruiterDocument.Status.REJECTED)
        document_admin.message_user.assert_called_once_with(
            request,
            ADMIN_EMAIL_WARNING,
            level=messages.WARNING,
        )
        self.assertEqual(captured.output, ['ERROR:accounts.email_delivery:Email delivery failed (RuntimeError)'])

    @override_settings(
        EMAIL_BACKEND='accounts.email_delivery.FailSafeEmailBackend',
        EMAIL_TRANSPORT_BACKEND='accounts.tests.FailingEmailBackend',
    )
    def test_password_reset_page_succeeds_when_email_backend_fails(self):
        user = User.objects.create_user(
            username='reset_user',
            email='reset@example.com',
            password=PASSWORD,
        )

        with self.assertLogs('accounts.email_delivery', level='ERROR') as captured:
            response = self.client.post(
                reverse('password_reset'),
                {'email': user.email},
            )

        self.assertIn(response.status_code, (200, 302))
        if response.status_code == 302:
            self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(captured.output, ['ERROR:accounts.email_delivery:Email delivery failed (RuntimeError)'])
        self.assertNotIn('654321', captured.output[0])
        self.assertNotIn('test-secret', captured.output[0])

    @override_settings(
        EMAIL_PROVIDER_CONFIGURED=True,
        EMAIL_BACKEND='accounts.tests.FailingEmailBackend',
    )
    def test_password_reset_is_failure_safe_with_direct_email_backend(self):
        user = User.objects.create_user(
            username='gmail_reset_user',
            email='gmail-reset@example.com',
            password=PASSWORD,
        )

        with self.assertLogs('accounts.email_delivery', level='ERROR') as captured:
            response = self.client.post(
                reverse('password_reset'),
                {'email': user.email},
            )

        self.assertIn(response.status_code, (200, 302))
        if response.status_code == 302:
            self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(
            captured.output,
            ['ERROR:accounts.email_delivery:Email delivery failed (RuntimeError)'],
        )
        self.assertNotIn('test-secret', captured.output[0])

    @override_settings(
        EMAIL_PROVIDER_CONFIGURED=False,
        EMAIL_BACKEND='django.core.mail.backends.dummy.EmailBackend',
    )
    def test_password_reset_remains_friendly_when_provider_is_unconfigured(self):
        user = User.objects.create_user(
            username='no_provider_reset',
            email='no_provider_reset@example.com',
            password=PASSWORD,
        )

        login_response = self.client.get(reverse('login'))
        self.assertContains(
            login_response,
            'Password reset by email is not available right now. Please contact the administrator.',
        )
        self.assertNotContains(login_response, 'Forgot password?')

        response = self.client.post(
            reverse('password_reset'),
            {'email': user.email},
        )
        self.assertIn(response.status_code, (200, 302))
        if response.status_code == 302:
            self.assertRedirects(response, reverse('password_reset_done'))


class RegistrationTests(TestCase):
    def setUp(self):
        cache.clear()

    def register(self, username, role):
        return self.client.post(reverse('register'), {
            'username': username,
            'email': f'{username}@example.com',
            'role': role,
            'password1': PASSWORD,
            'password2': PASSWORD,
        })

    @override_settings(REGISTER_OTP_REQUIRED=False)
    def test_home_and_register_hide_otp_copy_when_otp_is_disabled(self):
        home_response = self.client.get(reverse('home'))
        register_response = self.client.get(reverse('register'))

        self.assertNotContains(home_response, 'Accounts require email verification code confirmation')
        self.assertNotContains(register_response, 'A 6-digit verification code will be sent to this email')

    @override_settings(REGISTER_OTP_REQUIRED=True)
    def test_home_and_register_show_otp_copy_when_otp_is_enabled(self):
        home_response = self.client.get(reverse('home'))
        register_response = self.client.get(reverse('register'))

        self.assertContains(home_response, 'Accounts require email verification code confirmation')
        self.assertContains(register_response, 'A 6-digit verification code will be sent to this email')

    def test_candidate_registration_creates_profile(self):
        self.register('cand_test', 'candidate')
        user = User.objects.get(username='cand_test')
        self.assertEqual(user.role, 'candidate')
        self.assertTrue(CandidateProfile.objects.filter(user=user).exists())

    def test_recruiter_registration_creates_profile(self):
        self.register('rec_test', 'recruiter')
        user = User.objects.get(username='rec_test')
        self.assertEqual(user.role, 'recruiter')
        self.assertTrue(RecruiterProfile.objects.filter(user=user).exists())

    @override_settings(REGISTER_OTP_REQUIRED=True)
    @patch('accounts.views.send_email_otp', return_value=True)
    def test_registration_requires_otp_when_setting_enabled(self, send_otp):
        response = self.client.post(reverse('register'), {
            'username': 'otp_required',
            'email': 'otp_required@example.com',
            'role': 'candidate',
            'password1': PASSWORD,
            'password2': PASSWORD,
        })

        user = User.objects.get(username='otp_required')
        self.assertFalse(user.is_active)
        self.assertTrue(OTPCode.objects.filter(user=user, purpose=OTPCode.Purpose.REGISTER).exists())
        send_otp.assert_called_once()
        self.assertRedirects(response, reverse('verify_otp'))
        self.assertNotIn('_auth_user_id', self.client.session)

    @override_settings(REGISTER_OTP_REQUIRED=False)
    @patch('accounts.views.send_email_otp')
    def test_registration_skips_otp_when_setting_disabled(self, send_otp):
        response = self.client.post(reverse('register'), {
            'username': 'otp_not_required',
            'email': 'otp_not_required@example.com',
            'role': 'candidate',
            'password1': PASSWORD,
            'password2': PASSWORD,
        })

        user = User.objects.get(username='otp_not_required')
        self.assertTrue(user.is_active)
        self.assertFalse(OTPCode.objects.filter(user=user).exists())
        send_otp.assert_not_called()
        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_registration_shows_friendly_message_if_email_fails(self):
        with patch(
            'accounts.email_delivery.send_mail',
            side_effect=RuntimeError('OTP 123456 API key secret-value'),
        ):
            response = self.client.post(
                reverse('register'),
                {
                    'username': 'failed_email',
                    'email': 'failed_email@example.com',
                    'role': 'candidate',
                    'password1': PASSWORD,
                    'password2': PASSWORD,
                },
                follow=True,
            )

        self.assertContains(response, EMAIL_SEND_FAILURE_MESSAGE)
        self.assertEqual(response.status_code, 200)

    @override_settings(REGISTER_OTP_REQUIRED=True)
    @patch('accounts.views.OTPCode.generate_code', return_value='123456')
    @patch('accounts.views.send_email_otp', return_value=False)
    def test_failed_registration_send_is_truthful_and_has_recovery_actions(
        self,
        send_otp,
        _generate_code,
    ):
        response = self.client.post(
            reverse('register'),
            {
                'username': 'failed_code',
                'email': 'failed_code@example.com',
                'role': 'candidate',
                'password1': PASSWORD,
                'password2': PASSWORD,
            },
            follow=True,
        )

        self.assertContains(response, 'We could not send a code to')
        self.assertContains(response, 'f***e@example.com')
        self.assertNotContains(response, 'A code was sent to')
        self.assertContains(response, 'Resend code')
        self.assertContains(response, 'Change email')
        self.assertContains(response, 'Back to sign in')
        self.assertContains(response, 'data-seconds-left="60"')
        self.assertContains(response, '(available in 60s)')
        self.assertFalse(self.client.session['otp_send_succeeded'])
        send_otp.assert_called_once()

    @override_settings(REGISTER_OTP_REQUIRED=True)
    @patch('accounts.views.send_email_otp', return_value=True)
    def test_successful_send_is_shown_truthfully_and_change_email_prefills_form(self, send_otp):
        response = self.client.post(
            reverse('register'),
            {
                'username': 'sent_code',
                'email': 'sent_code@example.com',
                'role': 'candidate',
                'password1': PASSWORD,
                'password2': PASSWORD,
            },
            follow=True,
        )

        self.assertContains(response, 'A code was sent to')
        self.assertContains(response, 's***e@example.com')
        self.assertNotContains(response, 'We could not send a code to')
        self.assertContains(response, 'Back to sign in')
        self.assertContains(
            response,
            f'{reverse("register")}?username=sent_code&amp;email=sent_code%40example.com',
        )
        self.assertTrue(self.client.session['otp_send_succeeded'])
        register_response = self.client.get(
            reverse('register'),
            {'username': 'sent_code', 'email': 'sent_code@example.com'},
        )
        self.assertContains(register_response, 'value="sent_code"')
        self.assertContains(register_response, 'value="sent_code@example.com"')
        send_otp.assert_called_once()

    @override_settings(REGISTER_OTP_REQUIRED=True)
    @patch('accounts.views.send_email_otp', return_value=True)
    def test_verify_page_get_and_refresh_do_not_send_or_resubmit(self, send_otp):
        self.client.post(
            reverse('register'),
            {
                'username': 'refresh_code',
                'email': 'refresh_code@example.com',
                'role': 'candidate',
                'password1': PASSWORD,
                'password2': PASSWORD,
            },
        )
        verify_url = reverse('verify_otp')
        first_response = self.client.get(verify_url)
        second_response = self.client.get(verify_url)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(send_otp.call_count, 1)
        self.assertEqual(self.client.get(reverse('resend_otp')).status_code, 405)

    @override_settings(REGISTER_OTP_REQUIRED=True)
    @patch('accounts.views.OTPCode.generate_code', return_value='123456')
    @patch('accounts.views.send_email_otp', return_value=True)
    def test_invalid_code_post_redirects_and_refresh_does_not_repeat_attempt(
        self,
        send_otp,
        _generate_code,
    ):
        self.client.post(
            reverse('register'),
            {
                'username': 'invalid_code',
                'email': 'invalid_code@example.com',
                'role': 'candidate',
                'password1': PASSWORD,
                'password2': PASSWORD,
            },
        )
        otp = OTPCode.objects.get(user__username='invalid_code')

        response = self.client.post(reverse('verify_otp'), {'code': '999999'})
        self.assertRedirects(response, reverse('verify_otp'))
        self.assertEqual(OTPCode.objects.get(pk=otp.pk).attempts, 1)

        self.client.get(reverse('verify_otp'))
        self.assertEqual(OTPCode.objects.get(pk=otp.pk).attempts, 1)
        self.assertEqual(send_otp.call_count, 1)

    def test_rate_limited_verify_post_redirects_without_repeating_form_submission(self):
        user = User.objects.create_user(
            username='rate_limited_verify',
            email='rate_limited_verify@example.com',
            password=PASSWORD,
        )
        OTPCode.create_otp(user, OTPCode.Purpose.REGISTER)
        session = self.client.session
        session['pending_otp_user'] = user.pk
        session['otp_purpose'] = OTPCode.Purpose.REGISTER
        session.save()

        with patch('accounts.ratelimit.check_rate_limit', return_value=(False, 5)):
            response = self.client.post(reverse('verify_otp'), {'code': '999999'})

        self.assertRedirects(
            response,
            reverse('verify_otp'),
            fetch_redirect_response=False,
        )
        self.assertEqual(OTPCode.objects.get(user=user).attempts, 0)

    def test_lost_verification_session_redirects_to_register(self):
        response = self.client.get(reverse('verify_otp'), follow=True)

        self.assertRedirects(response, reverse('register'))
        self.assertContains(response, 'Your verification session expired. Please register again.')

    @override_settings(REGISTER_OTP_REQUIRED=True)
    @patch('accounts.views.OTPCode.can_resend', return_value=(True, ''))
    @patch('accounts.views.send_email_otp', return_value=False)
    def test_failed_resend_updates_session_and_verify_message(self, send_otp, _can_resend):
        self.client.post(
            reverse('register'),
            {
                'username': 'resend_failed',
                'email': 'resend_failed@example.com',
                'role': 'candidate',
                'password1': PASSWORD,
                'password2': PASSWORD,
            },
        )

        response = self.client.post(reverse('resend_otp'), follow=True)

        self.assertContains(response, 'We could not send a code to')
        self.assertNotContains(response, 'A code was sent to')
        self.assertFalse(self.client.session['otp_send_succeeded'])
        self.assertEqual(send_otp.call_count, 2)

    @override_settings(REGISTER_OTP_REQUIRED=True)
    @patch('accounts.views.send_email_otp', return_value=True)
    def test_registration_replaces_matching_unverified_username_and_email(self, send_otp):
        old_user = User.objects.create_user(
            username='Retry_Registration',
            email='retry_registration@example.com',
            password=PASSWORD,
        )
        old_user.is_active = False
        old_user.save(update_fields=['is_active'])

        response = self.client.post(
            reverse('register'),
            {
                'username': 'retry_registration',
                'email': 'retry_registration@example.com',
                'role': 'candidate',
                'password1': PASSWORD,
                'password2': PASSWORD,
            },
        )

        self.assertRedirects(response, reverse('verify_otp'))
        new_user = User.objects.get(username='retry_registration')
        self.assertNotEqual(new_user.pk, old_user.pk)
        self.assertFalse(new_user.is_active)
        send_otp.assert_called_once()

    @override_settings(REGISTER_OTP_REQUIRED=True)
    @patch('accounts.views.send_email_otp', return_value=True)
    def test_registration_replaces_unverified_account_matching_email_only(self, send_otp):
        old_user = User.objects.create_user(
            username='old_email_user',
            email='reused_email@example.com',
            password=PASSWORD,
        )
        old_user.is_active = False
        old_user.save(update_fields=['is_active'])

        response = self.client.post(
            reverse('register'),
            {
                'username': 'new_email_user',
                'email': 'reused_email@example.com',
                'role': 'candidate',
                'password1': PASSWORD,
                'password2': PASSWORD,
            },
        )

        self.assertRedirects(response, reverse('verify_otp'))
        new_user = User.objects.get(username='new_email_user')
        self.assertFalse(User.objects.filter(pk=old_user.pk).exists())
        self.assertEqual(new_user.email, 'reused_email@example.com')
        send_otp.assert_called_once()

    def test_registration_never_deletes_active_account_conflicts(self):
        active_user = User.objects.create_user(
            username='Active_Registration',
            email='active_registration@example.com',
            password=PASSWORD,
        )
        inactive_user = User.objects.create_user(
            username='inactive_email_conflict',
            email='inactive_email@example.com',
            password=PASSWORD,
        )
        inactive_user.is_active = False
        inactive_user.save(update_fields=['is_active'])

        username_conflict_response = self.client.post(
            reverse('register'),
            {
                'username': 'active_registration',
                'email': 'new_email@example.com',
                'role': 'candidate',
                'password1': PASSWORD,
                'password2': PASSWORD,
            },
        )
        self.assertEqual(username_conflict_response.status_code, 200)
        self.assertTrue(User.objects.filter(pk=active_user.pk, is_active=True).exists())

        response = self.client.post(
            reverse('register'),
            {
                'username': 'inactive_email_conflict',
                'email': active_user.email,
                'role': 'candidate',
                'password1': PASSWORD,
                'password2': PASSWORD,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(pk=active_user.pk, is_active=True).exists())
        self.assertTrue(User.objects.filter(pk=inactive_user.pk, is_active=False).exists())

    def test_delete_unverified_accounts_dry_run_and_verified_account_protection(self):
        stale = User.objects.create_user(
            username='stale_unverified',
            email='stale_unverified@example.com',
            password=PASSWORD,
        )
        recent = User.objects.create_user(
            username='recent_unverified',
            email='recent_unverified@example.com',
            password=PASSWORD,
        )
        verified_then_inactive = User.objects.create_user(
            username='verified_inactive',
            email='verified_inactive@example.com',
            password=PASSWORD,
        )
        active = User.objects.create_user(
            username='active_old_user',
            email='active_old_user@example.com',
            password=PASSWORD,
        )
        User.objects.filter(pk__in=[stale.pk, recent.pk, verified_then_inactive.pk]).update(
            is_active=False,
        )
        old_date = timezone.now() - timedelta(hours=25)
        User.objects.filter(pk__in=[stale.pk, verified_then_inactive.pk, active.pk]).update(
            date_joined=old_date,
        )
        OTPCode.objects.create(
            user=verified_then_inactive,
            channel=OTPCode.Channel.EMAIL,
            code_hash='unused-test-hash',
            purpose=OTPCode.Purpose.REGISTER,
            expires_on=timezone.now() + timedelta(minutes=10),
            is_used=True,
        )

        output = StringIO()
        call_command('delete_unverified_accounts', '--dry-run', stdout=output)
        self.assertIn('1 unverified account(s) would be deleted', output.getvalue())
        self.assertTrue(User.objects.filter(pk=stale.pk).exists())

        call_command('delete_unverified_accounts', stdout=StringIO())
        self.assertFalse(User.objects.filter(pk=stale.pk).exists())
        self.assertTrue(User.objects.filter(pk=recent.pk).exists())
        self.assertTrue(User.objects.filter(pk=verified_then_inactive.pk).exists())
        self.assertTrue(User.objects.filter(pk=active.pk, is_active=True).exists())

    def test_cannot_register_as_admin(self):
        response = self.register('sneaky', 'admin')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='sneaky').exists())

    def test_profile_requires_login(self):
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 302)

    @patch('accounts.views.send_email_otp')
    def test_inactive_user_can_resume_registration_verification_from_login(self, send_otp):
        self.register('pending_registration', 'candidate')
        user = User.objects.get(username='pending_registration')
        self.assertFalse(user.is_active)
        registration_code = send_otp.call_args.args[1]

        response = self.client.post(reverse('login'), {
            'username': user.username,
            'password': PASSWORD,
        })
        self.assertRedirects(response, reverse('verify_otp'))
        self.assertEqual(send_otp.call_count, 1)

        response = self.client.post(reverse('verify_otp'), {'code': registration_code})
        self.assertRedirects(response, reverse('dashboard'))
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    @patch('accounts.views.send_email_otp')
    @override_settings(LOGIN_OTP_REQUIRED=True)
    def test_active_user_must_verify_login_otp(self, send_otp):
        user = User.objects.create_user(
            username='otp_login', email='otp_login@example.com', password=PASSWORD,
        )
        response = self.client.post(reverse('login'), {
            'username': user.username,
            'password': PASSWORD,
        })
        self.assertRedirects(response, reverse('verify_otp'))
        self.assertEqual(send_otp.call_args.kwargs['purpose'], 'login')

        response = self.client.post(
            reverse('verify_otp'),
            {'code': send_otp.call_args.args[1]},
        )
        self.assertRedirects(response, reverse('dashboard'))


class RecruiterVerificationTests(TestCase):
    def setUp(self):
        self.rec1 = User.objects.create_user(
            username='rec1', email='hr@acmecorp.com', password=PASSWORD, role=User.Role.RECRUITER
        )
        self.rec2 = User.objects.create_user(
            username='rec2', email='hr@other.com', password=PASSWORD, role=User.Role.RECRUITER
        )

    def test_duplicate_verified_company_name_blocked(self):
        # rec1 is verified with Acme Corp
        self.rec1.recruiter_profile.company_name = 'Acme Corp'
        self.rec1.recruiter_profile.company_website = 'https://acmecorp.com'
        self.rec1.recruiter_profile.is_verified = True
        self.rec1.recruiter_profile.save()

        # rec2 tries to save 'acme corp' (case-insensitive)
        self.client.login(username='rec2', password=PASSWORD)
        response = self.client.post(reverse('profile'), {
            'company_name': 'acme corp',
            'company_website': 'https://acmecorp.com',
            'location': 'Bangalore',
            'designation': 'HR',
            'about_company': 'Copycat',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already exists')

        # rec2's company was NOT updated
        self.rec2.recruiter_profile.refresh_from_db()
        self.assertNotEqual(self.rec2.recruiter_profile.company_name, 'acme corp')

    def test_duplicate_unverified_company_name_allowed(self):
        # rec1 has company name but is NOT verified
        self.rec1.recruiter_profile.company_name = 'Beta Tech'
        self.rec1.recruiter_profile.company_website = 'https://betatech.com'
        self.rec1.recruiter_profile.is_verified = False
        self.rec1.recruiter_profile.save()

        # rec2 can also save 'Beta Tech'
        self.client.login(username='rec2', password=PASSWORD)
        response = self.client.post(reverse('profile'), {
            'company_name': 'Beta Tech',
            'company_website': 'https://betatech.com',
            'company_email': 'hr@betatech.com',
            'address': 'Chennai, Tamil Nadu',
            'location': 'Chennai',
            'designation': 'HR Lead',
            'about_company': 'Legit Beta',
        })
        self.assertEqual(response.status_code, 302)
        self.rec2.recruiter_profile.refresh_from_db()
        self.assertEqual(self.rec2.recruiter_profile.company_name, 'Beta Tech')

    def test_recruiter_website_validation(self):
        self.client.login(username='rec1', password=PASSWORD)

        # Missing website fails
        response = self.client.post(reverse('profile'), {
            'company_name': 'New Tech',
            'company_website': '',
            'location': 'Chennai',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This field is required.')

        # Invalid URL fails
        response = self.client.post(reverse('profile'), {
            'company_name': 'New Tech',
            'company_website': 'not-a-valid-url',
            'location': 'Chennai',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enter a valid URL.')

        # Valid URL succeeds
        response = self.client.post(reverse('profile'), {
            'company_name': 'New Tech',
            'company_website': 'https://newtech.io',
            'company_email': 'hr@newtech.io',
            'address': 'Chennai, Tamil Nadu',
            'location': 'Chennai',
        })
        self.assertEqual(response.status_code, 302)
        self.rec1.recruiter_profile.refresh_from_db()
        self.assertEqual(self.rec1.recruiter_profile.company_website, 'https://newtech.io')

    def test_domain_match_check_helper(self):
        # Public domains flagged
        flagged, reason = check_recruiter_domain_match('user@gmail.com', 'https://example.com')
        self.assertTrue(flagged)
        self.assertIn('gmail.com', reason)

        flagged, reason = check_recruiter_domain_match('user@yahoo.com', 'https://example.com')
        self.assertTrue(flagged)
        self.assertIn('yahoo.com', reason)

        flagged, reason = check_recruiter_domain_match('user@outlook.com', 'https://example.com')
        self.assertTrue(flagged)
        self.assertIn('outlook.com', reason)

        # Mismatch flagged
        flagged, reason = check_recruiter_domain_match('user@abc.com', 'https://xyz.com')
        self.assertTrue(flagged)
        self.assertIn('mismatch', reason.lower())

        # Match succeeds
        flagged, reason = check_recruiter_domain_match('hr@google.com', 'https://www.google.com')
        self.assertFalse(flagged)

    def test_admin_verify_and_unverify_actions(self):
        admin_site = AdminSite()
        profile_admin = RecruiterProfileAdmin(RecruiterProfile, admin_site)

        p1 = self.rec1.recruiter_profile
        self.assertFalse(p1.is_verified)

        qs = RecruiterProfile.objects.filter(pk=p1.pk)
        profile_admin.verify_recruiters(None, qs)

        p1.refresh_from_db()
        self.assertTrue(p1.is_verified)
        self.assertIsNotNone(p1.verified_on)

        profile_admin.unverify_recruiters(None, qs)
        p1.refresh_from_db()
        self.assertFalse(p1.is_verified)
        self.assertIsNone(p1.verified_on)


class RecruiterDocumentUploadTests(TestCase):
    def setUp(self):
        self.recruiter = User.objects.create_user(
            username='document_recruiter',
            email='hr@documents.example',
            password=PASSWORD,
            role=User.Role.RECRUITER,
        )
        self.client.force_login(self.recruiter)

    def test_document_upload_requires_complete_company_details(self):
        upload = SimpleUploadedFile(
            'registration.pdf',
            b'%PDF-1.4 test document',
            content_type='application/pdf',
        )

        response = self.client.post(reverse('company_verification'), {
            'document_type': RecruiterDocument.DocType.REGISTRATION,
            'description': '',
            'file': upload,
        })

        self.assertRedirects(response, reverse('company_verification'))
        self.assertFalse(RecruiterDocument.objects.exists())

    def test_recruiter_can_upload_proof_after_completing_company_details(self):
        profile = self.recruiter.recruiter_profile
        profile.company_name = 'Document Company'
        profile.company_website = 'https://documents.example'
        profile.company_email = 'hr@documents.example'
        profile.address = '123 Main Street, Chennai'
        profile.save()
        upload = SimpleUploadedFile(
            'registration.pdf',
            b'%PDF-1.4 test document',
            content_type='application/pdf',
        )

        response = self.client.post(reverse('company_verification'), {
            'document_type': RecruiterDocument.DocType.REGISTRATION,
            'description': '',
            'file': upload,
        })

        self.assertRedirects(response, reverse('company_verification'))
        document = RecruiterDocument.objects.get(recruiter=profile)
        self.assertEqual(document.status, RecruiterDocument.Status.PENDING)
        self.assertEqual(document.file_data, b'%PDF-1.4 test document')
