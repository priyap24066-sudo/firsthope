import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from jobs.tests import PASSWORD, make_job, make_user
from .models import Application

TEMP_MEDIA = tempfile.mkdtemp()


def pdf(name='resume.pdf'):
    return SimpleUploadedFile(name, b'%PDF-1.4 test', content_type='application/pdf')


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ApplicationTests(TestCase):
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

    def make_application(self):
        return Application.objects.create(
            job=self.job, candidate=self.cand1, resume=pdf()
        )

    def apply(self, file):
        return self.client.post(
            reverse('apply_job', args=[self.job.pk]),
            {'resume': file, 'cover_letter': 'Hello'},
        )

    def test_candidate_can_apply(self):
        self.client.login(username='cand1', password=PASSWORD)
        self.apply(pdf())
        self.assertEqual(Application.objects.count(), 1)

    def test_cannot_apply_twice(self):
        self.client.login(username='cand1', password=PASSWORD)
        self.apply(pdf())
        self.apply(pdf('second.pdf'))
        self.assertEqual(Application.objects.count(), 1)

    def test_wrong_file_type_rejected(self):
        self.client.login(username='cand1', password=PASSWORD)
        bad = SimpleUploadedFile('photo.jpg', b'abc', content_type='image/jpeg')
        self.apply(bad)
        self.assertEqual(Application.objects.count(), 0)

    def test_recruiter_cannot_apply(self):
        self.client.login(username='rec1', password=PASSWORD)
        response = self.client.get(reverse('apply_job', args=[self.job.pk]))
        self.assertEqual(response.status_code, 403)

    def test_cannot_apply_to_closed_job(self):
        self.job.is_active = False
        self.job.save()
        self.client.login(username='cand1', password=PASSWORD)
        response = self.client.get(reverse('apply_job', args=[self.job.pk]))
        self.assertEqual(response.status_code, 404)

    def test_owner_recruiter_can_change_status(self):
        app = self.make_application()
        self.client.login(username='rec1', password=PASSWORD)
        self.client.post(reverse('update_status', args=[app.pk]), {'status': 'shortlisted'})
        app.refresh_from_db()
        self.assertEqual(app.status, 'shortlisted')

    def test_invalid_status_ignored(self):
        app = self.make_application()
        self.client.login(username='rec1', password=PASSWORD)
        self.client.post(reverse('update_status', args=[app.pk]), {'status': 'abc'})
        app.refresh_from_db()
        self.assertEqual(app.status, 'applied')

    def test_other_recruiter_cannot_change_status(self):
        app = self.make_application()
        self.client.login(username='rec2', password=PASSWORD)
        response = self.client.post(
            reverse('update_status', args=[app.pk]), {'status': 'hired'}
        )
        self.assertEqual(response.status_code, 404)
        app.refresh_from_db()
        self.assertEqual(app.status, 'applied')

    def test_candidate_cannot_see_applicants_page(self):
        self.client.login(username='cand1', password=PASSWORD)
        response = self.client.get(reverse('job_applicants', args=[self.job.pk]))
        self.assertEqual(response.status_code, 403)

    def test_resume_download_permissions(self):
        app = self.make_application()
        url = reverse('download_resume', args=[app.pk])

        # not logged in
        self.assertEqual(self.client.get(url).status_code, 302)

        # owner candidate and owner recruiter can open it
        for username in ('cand1', 'rec1'):
            self.client.login(username=username, password=PASSWORD)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            response.close()
            self.client.logout()

        # others cannot
        for username in ('cand2', 'rec2'):
            self.client.login(username=username, password=PASSWORD)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.client.logout()