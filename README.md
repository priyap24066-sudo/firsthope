# FirstHope - Job Recruitment & Applicant Tracking System

FirstHope is a web application where recruiters post jobs and candidates apply and track their applications. It also supports interview scheduling and has a REST API.

**Live demo:** https://firsthope.onrender.com

## Features

**Recruiter**
- Register and manage a company profile
- Post and manage jobs
- Review applications and update status (Applied, Shortlisted, Rejected, Hired)
- Schedule interviews (Scheduled, Completed, Cancelled)

**Candidate**
- Register and manage a profile
- Upload a resume
- Browse jobs without logging in
- Apply for jobs with a cover letter (login required)
- Track application status and view interviews

**General**
- Separate dashboards for recruiters and candidates
- Admin panel for managing users and data
- REST API built with Django REST Framework
- Mobile-friendly design with a hamburger menu
- Installable as a Progressive Web App (PWA)

## Tech Stack

- **Backend:** Django, Django REST Framework
- **Database:** PostgreSQL (production on Render), SQLite (local development)
- **Frontend:** HTML, CSS, JavaScript
- **Deployment:** Render, GitHub, WhiteNoise

## REST API

The API provides JSON endpoints for:

- `/api/jobs/`
- `/api/applications/`
- `/api/interviews/`
- `/api/me/`

## Run Locally

```bash
git clone https://github.com/priyap24066-sudo/firsthope.git
cd firsthope
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/ in your browser.

## Environment Variables (Production)

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | Django secret key |
| `ALLOWED_HOSTS` | Allowed domain names |
| `DEBUG` | Set to `False` in production |

Secrets are not stored in the code. They are set in the Render dashboard.

## Future Scope

- Email notifications for application and interview updates
- Automatic resume parsing to fill profile details
- Job search and filters
- In-app chat between recruiters and candidates
- Forgot password via email
- Cloud storage (AWS S3 or Cloudinary) for uploaded resumes

## Author

Developed by Priya