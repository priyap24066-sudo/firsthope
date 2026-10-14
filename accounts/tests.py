from django.test import TestCase
from django.urls import reverse

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