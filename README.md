# FirstHope – Job Portal

FirstHope is a Django-based job portal designed to connect job seekers with recruiters. Candidates can explore job opportunities and manage their applications, while recruiters can post jobs and manage applicants.

## Features

- User registration and login
- Candidate and recruiter profiles
- Job listing and job details
- Job posting and management
- Job application management
- Candidate and recruiter dashboards
- Interview scheduling
- REST API integration
- Access control and permissions

## Technologies Used

- **Backend:** Python, Django
- **Frontend:** HTML, CSS, JavaScript, Bootstrap
- **Database:** SQLite (if configured in the project)
- **API:** Django REST Framework (if configured)

## Project Structure

- `accounts/` – User accounts and profiles
- `jobs/` – Job posting and listings
- `applications/` – Job applications
- `interviews/` – Interview scheduling
- `dashboard/` – User dashboards
- `restapi/` – API components
- `config/` – Django project configuration
- `templates/` – HTML templates

## Installation and Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/priyap24066-sudo/firsthope.git
   ```

2. Navigate to the project folder:

   ```bash
   cd firsthope
   ```

3. Create and activate a virtual environment:

   ```bash
   python -m venv venv
   ```

   Windows PowerShell:

   ```powershell
   venv\Scripts\Activate.ps1
   ```

4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Apply database migrations:

   ```bash
   python manage.py migrate
   ```

6. Start the development server:

   ```bash
   python manage.py runserver
   ```

7. Open `http://127.0.0.1:8000/` in your browser.

## Author

Priya Mani

BCA Graduate | Aspiring Python Full Stack Developer
