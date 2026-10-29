from django.contrib.admin.sites import AdminSite
from django.test import TestCase
from django.urls import reverse

from .admin import RecruiterProfileAdmin, check_recruiter_domain_match
from .models import CandidateProfile, RecruiterProfile, User

PASSWORD = 'Str0ng!Pass#2026'


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

    def test_cannot_register_as_admin(self):
        response = self.register('sneaky', 'admin')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='sneaky').exists())

    def test_profile_requires_login(self):
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 302)


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
