import os
import runpy
from pathlib import Path
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .admin import RecruiterProfileAdmin, check_recruiter_domain_match
from .email_delivery import EMAIL_SEND_FAILURE_MESSAGE
from .models import CandidateProfile, OTPCode, RecruiterDocument, RecruiterProfile, User
from .otp_sender import send_email_otp

PASSWORD = 'Str0ng!Pass#2026'


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

        self.assertEqual(configured['EMAIL_BACKEND'], 'anymail.backends.brevo.EmailBackend')
        self.assertEqual(configured['ANYMAIL'], {'BREVO_API_KEY': 'test-brevo-key'})
        self.assertIn('anymail', configured['INSTALLED_APPS'])
        self.assertEqual(configured['DEFAULT_FROM_EMAIL'], 'FirstHope <verified@example.com>')

    def test_console_backend_remains_default_without_email_host_or_brevo_key(self):
        configured = self.load_settings({'BREVO_API_KEY': '', 'EMAIL_HOST': ''})

        self.assertEqual(
            configured['EMAIL_BACKEND'],
            'django.core.mail.backends.console.EmailBackend',
        )

    def test_smtp_backend_remains_available_without_brevo_key(self):
        configured = self.load_settings({'BREVO_API_KEY': '', 'EMAIL_HOST': 'smtp.example.com'})

        self.assertEqual(
            configured['EMAIL_BACKEND'],
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


class RegistrationTests(TestCase):
    def register(self, username, role):
        return self.client.post(reverse('register'), {
            'username': username,
            'email': f'{username}@example.com',
            'role': role,
            'password1': PASSWORD,
            'password2': PASSWORD,
        })

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
