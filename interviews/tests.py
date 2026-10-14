from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from applications.models import Application
from jobs.tests import PASSWORD, make_job, make_user
from .models import Interview


def when(days):
    value = timezone.localtime() + timedelta(days=days)
    return value.strftime('%Y-%m-%dT%H:%M')


class InterviewTests(TestCase):
    def setUp(self):
        self.rec1 = make_user('rec1', 'recruiter')
        self.rec2 = make_user('rec2', 'recruiter')
        self.cand = make_user('cand', 'candidate')
        self.job = make_job(self.rec1)
        self.app = Application.objects.create(
            job=self.job, candidate=self.cand,
            resume='resumes/test.pdf', status='shortlisted',
        )
        self.url = reverse('schedule_interview', args=[self.app.pk])

    def data(self, **kwargs):
        data = {
            'scheduled_at': when(2), 'mode': 'online',
            'location_or_link': 'https://meet.google.com/abc-defg-hij', 'notes': '',
        }
        data.update(kwargs)
        return data

    def test_recruiter_can_schedule(self):
        self.client.login(username='rec1', password=PASSWORD)
        response = self.client.post(self.url, self.data())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Interview.objects.count(), 1)

    def test_only_shortlisted_candidates(self):
        self.app.status = 'applied'
        self.app.save()
        self.client.login(username='rec1', password=PASSWORD)
        self.client.post(self.url, self.data())
        self.assertEqual(Interview.objects.count(), 0)

    def test_past_date_rejected(self):
        self.client.login(username='rec1', password=PASSWORD)
        self.client.post(self.url, self.data(scheduled_at=when(-1)))
        self.assertEqual(Interview.objects.count(), 0)

    def test_online_link_must_be_http(self):
        self.client.login(username='rec1', password=PASSWORD)
        self.client.post(self.url, self.data(location_or_link='meet.google.com/abc'))
        self.assertEqual(Interview.objects.count(), 0)

    def test_in_person_needs_no_link(self):
        self.client.login(username='rec1', password=PASSWORD)
        self.client.post(
            self.url, self.data(mode='in_person', location_or_link='Coimbatore office')
        )
        self.assertEqual(Interview.objects.count(), 1)

    def test_candidate_cannot_schedule(self):
        self.client.login(username='cand', password=PASSWORD)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_other_recruiter_cannot_schedule(self):
        self.client.login(username='rec2', password=PASSWORD)
        response = self.client.post(self.url, self.data())
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Interview.objects.count(), 0)

    def test_complete_interview(self):
        interview = Interview.objects.create(
            application=self.app, scheduled_at=timezone.now() + timedelta(days=1),
            mode='phone', location_or_link='9876543210',
        )
        self.client.login(username='rec1', password=PASSWORD)
        self.client.post(
            reverse('update_interview_status', args=[interview.pk]),
            {'status': 'completed'},
        )
        interview.refresh_from_db()
        self.assertEqual(interview.status, 'completed')

    def test_candidate_sees_only_own_interviews(self):
        other = make_user('cand2', 'candidate')
        Interview.objects.create(
            application=self.app, scheduled_at=timezone.now() + timedelta(days=1),
            mode='phone', location_or_link='1111111111',
        )
        self.client.login(username='cand2', password=PASSWORD)
        response = self.client.get(reverse('my_interviews'))
        self.assertNotContains(response, '1111111111')