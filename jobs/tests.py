from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from .models import Job, JobReport

PASSWORD = 'Test@12345'


def make_user(username, role, verified=True):
    user = User.objects.create_user(username=username, password=PASSWORD, role=role)
    if role == 'recruiter' and verified and hasattr(user, 'recruiter_profile'):
        user.recruiter_profile.is_verified = True
        user.recruiter_profile.verified_on = timezone.now()
        user.recruiter_profile.save()
    return user


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
        self.assertContains(response, 'Verified')

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

    # --- Verification & Reporting Tests ---

    def test_unverified_recruiter_cannot_post_job(self):
        unverified_rec = make_user('unver_rec', 'recruiter', verified=False)
        self.client.login(username='unver_rec', password=PASSWORD)

        # Unverified recruiters are sent to submit proof documents.
        response = self.client.get(reverse('job_create'), follow=True)
        self.assertRedirects(response, reverse('company_verification'))
        self.assertContains(response, 'Upload your company proof to start posting jobs')

        # POST request also blocked
        response = self.client.post(reverse('job_create'), {
            'title': 'Blocked Job', 'company_name': 'FakeCo', 'location': 'Nowhere',
            'job_type': 'full_time', 'skills_required': 'Python', 'description': 'Fake',
        }, follow=True)
        self.assertRedirects(response, reverse('company_verification'))
        self.assertFalse(Job.objects.filter(title='Blocked Job').exists())

    def test_unverified_recruiter_jobs_hidden_from_public_list_and_detail(self):
        unverified_rec = make_user('unver_rec2', 'recruiter', verified=False)
        job = make_job(unverified_rec, title='Secret Job')

        # Hidden from public list
        response = self.client.get(reverse('job_list'))
        self.assertNotContains(response, 'Secret Job')

        # Detail page returns 404 for anonymous user and candidate
        response = self.client.get(reverse('job_detail', args=[job.pk]))
        self.assertEqual(response.status_code, 404)

        self.client.login(username='cand', password=PASSWORD)
        response = self.client.get(reverse('job_detail', args=[job.pk]))
        self.assertEqual(response.status_code, 404)

        # But recruiter owner can view their own job detail
        self.client.login(username='unver_rec2', password=PASSWORD)
        response = self.client.get(reverse('job_detail', args=[job.pk]))
        self.assertEqual(response.status_code, 200)

    def test_candidate_can_report_job_only_once(self):
        job = make_job(self.rec1, title='Suspicious Job')
        self.client.login(username='cand', password=PASSWORD)

        # First report succeeds
        response = self.client.post(reverse('report_job', args=[job.pk]), {
            'reason': 'Asking for registration fee',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(JobReport.objects.filter(job=job, reported_by=self.cand).count(), 1)

        # Second report attempt is blocked
        response = self.client.post(reverse('report_job', args=[job.pk]), {
            'reason': 'Second attempt to report',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'You have already reported this job.')
        self.assertEqual(JobReport.objects.filter(job=job, reported_by=self.cand).count(), 1)

    def test_job_auto_deactivated_after_3_reports(self):
        job = make_job(self.rec1, title='Scam Job')
        self.assertTrue(job.is_active)

        c1 = make_user('reporter1', 'candidate')
        c2 = make_user('reporter2', 'candidate')
        c3 = make_user('reporter3', 'candidate')

        # 1st report
        self.client.login(username='reporter1', password=PASSWORD)
        self.client.post(reverse('report_job', args=[job.pk]), {'reason': 'Fake job 1'})
        job.refresh_from_db()
        self.assertTrue(job.is_active)

        # 2nd report
        self.client.login(username='reporter2', password=PASSWORD)
        self.client.post(reverse('report_job', args=[job.pk]), {'reason': 'Fake job 2'})
        job.refresh_from_db()
        self.assertTrue(job.is_active)

        # 3rd report -> triggers deactivation
        self.client.login(username='reporter3', password=PASSWORD)
        response = self.client.post(reverse('report_job', args=[job.pk]), {'reason': 'Fake job 3'}, follow=True)
        self.assertEqual(response.status_code, 200)

        job.refresh_from_db()
        self.assertFalse(job.is_active)

        # Job is now hidden from public list
        list_response = self.client.get(reverse('job_list'))
        self.assertNotContains(list_response, 'Scam Job')

    def test_recruiter_cannot_report_job(self):
        job = make_job(self.rec1)
        self.client.login(username='rec2', password=PASSWORD)
        response = self.client.post(reverse('report_job', args=[job.pk]), {'reason': 'Competitor'})
        self.assertEqual(response.status_code, 403)
