import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from applications.models import Application
from jobs.tests import make_job, make_user

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ApiTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.rec1 = make_user('rec1', 'recruiter')
        self.rec2 = make_user('rec2', 'recruiter')
        self.cand1 = make_user('cand1', 'candidate')
        self.cand2 = make_user('cand2', 'candidate')
        self.job = make_job(self.rec1)

    def test_job_list_is_public(self):
        response = self.client.get('/api/jobs/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

    def test_closed_jobs_hidden(self):
        make_job(self.rec1, title='Closed', is_active=False)
        response = self.client.get('/api/jobs/')
        self.assertEqual(response.data['count'], 1)

    def test_me_requires_login(self):
        response = self.client.get('/api/me/')
        self.assertIn(response.status_code, (401, 403))

    def test_candidate_cannot_create_job(self):
        self.client.force_authenticate(user=self.cand1)
        response = self.client.post('/api/jobs/', {'title': 'X'}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_recruiter_can_create_job(self):
        self.client.force_authenticate(user=self.rec1)
        response = self.client.post('/api/jobs/', {
            'title': 'API Job', 'company_name': 'TestCo', 'location': 'Chennai',
            'job_type': 'full_time', 'skills_required': 'Python',
            'description': 'Created by API',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['recruiter'], 'rec1')

    def test_recruiter_cannot_edit_other_recruiters_job(self):
        self.client.force_authenticate(user=self.rec2)
        response = self.client.patch(
            f'/api/jobs/{self.job.pk}/', {'title': 'Hacked'}, format='json'
        )
        self.assertEqual(response.status_code, 404)

    def test_candidate_sees_only_own_applications(self):
        Application.objects.create(job=self.job, candidate=self.cand1, resume='resumes/a.pdf')
        Application.objects.create(job=self.job, candidate=self.cand2, resume='resumes/b.pdf')
        self.client.force_authenticate(user=self.cand1)
        response = self.client.get('/api/applications/')
        self.assertEqual(response.data['count'], 1)

    def test_other_recruiter_cannot_change_status(self):
        app = Application.objects.create(
            job=self.job, candidate=self.cand1, resume='resumes/a.pdf'
        )
        self.client.force_authenticate(user=self.rec2)
        response = self.client.patch(
            f'/api/applications/{app.pk}/status/', {'status': 'hired'}, format='json'
        )
        self.assertEqual(response.status_code, 404)

    def test_owner_can_change_status(self):
        app = Application.objects.create(
            job=self.job, candidate=self.cand1, resume='resumes/a.pdf'
        )
        self.client.force_authenticate(user=self.rec1)
        response = self.client.patch(
            f'/api/applications/{app.pk}/status/', {'status': 'shortlisted'}, format='json'
        )
        self.assertEqual(response.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'shortlisted')

    def test_api_apply_and_resume_link_is_protected(self):
        self.client.force_authenticate(user=self.cand1)
        file = SimpleUploadedFile('r.pdf', b'%PDF-1.4 x', content_type='application/pdf')
        response = self.client.post(
            '/api/applications/',
            {'job': self.job.pk, 'resume': file, 'cover_letter': 'Hi'},
            format='multipart',
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn('/resume/', response.data['resume'])
        self.assertNotIn('/media/', response.data['resume'])

        again = SimpleUploadedFile('r2.pdf', b'%PDF-1.4 y', content_type='application/pdf')
        second = self.client.post(
            '/api/applications/',
            {'job': self.job.pk, 'resume': again},
            format='multipart',
        )
        self.assertEqual(second.status_code, 400)