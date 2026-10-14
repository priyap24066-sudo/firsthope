from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from .models import Job

PASSWORD = 'Test@12345'


def make_user(username, role):
    return User.objects.create_user(username=username, password=PASSWORD, role=role)


def make_job(recruiter, title='Django Developer', **kwargs):
    data = dict(
        title=title, company_name='TestCo', location='Chennai',
        job_type='full_time', skills_required='Python, Django',
        description='Test job', is_active=True,
    )
    data.update(kwargs)
    return Job.objects.create(recruiter=recruiter, **data)


class JobTests(TestCase):
    def setUp(self):
        self.rec1 = make_user('rec1', 'recruiter')
        self.rec2 = make_user('rec2', 'recruiter')
        self.cand = make_user('cand', 'candidate')

    def test_job_list_is_public(self):
        make_job(self.rec1)
        response = self.client.get(reverse('job_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Django Developer')

    def test_inactive_job_hidden_from_list(self):
        make_job(self.rec1, title='Closed Job', is_active=False)
        response = self.client.get(reverse('job_list'))
        self.assertNotContains(response, 'Closed Job')

    def test_search_by_title(self):
        make_job(self.rec1, title='Python Developer')
        make_job(self.rec1, title='Java Developer', skills_required='Java')
        response = self.client.get(reverse('job_list'), {'q': 'python'})
        self.assertContains(response, 'Python Developer')
        self.assertNotContains(response, 'Java Developer')

    def test_job_create_requires_login(self):
        response = self.client.get(reverse('job_create'))
        self.assertEqual(response.status_code, 302)

    def test_candidate_cannot_post_job(self):
        self.client.login(username='cand', password=PASSWORD)
        response = self.client.get(reverse('job_create'))
        self.assertEqual(response.status_code, 403)

    def test_recruiter_can_post_job(self):
        self.client.login(username='rec1', password=PASSWORD)
        response = self.client.post(reverse('job_create'), {
            'title': 'New Job', 'company_name': 'TestCo', 'location': 'Madurai',
            'job_type': 'full_time', 'salary': '3 LPA',
            'skills_required': 'Python', 'description': 'Desc', 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        job = Job.objects.get(title='New Job')
        self.assertEqual(job.recruiter, self.rec1)

    def test_recruiter_cannot_edit_other_recruiters_job(self):
        job = make_job(self.rec1)
        self.client.login(username='rec2', password=PASSWORD)
        response = self.client.get(reverse('job_edit', args=[job.pk]))
        self.assertEqual(response.status_code, 404)

    def test_recruiter_cannot_delete_other_recruiters_job(self):
        job = make_job(self.rec1)
        self.client.login(username='rec2', password=PASSWORD)
        response = self.client.post(reverse('job_delete', args=[job.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Job.objects.filter(pk=job.pk).exists())

    def test_owner_can_delete_job(self):
        job = make_job(self.rec1)
        self.client.login(username='rec1', password=PASSWORD)
        self.client.post(reverse('job_delete', args=[job.pk]))
        self.assertFalse(Job.objects.filter(pk=job.pk).exists())