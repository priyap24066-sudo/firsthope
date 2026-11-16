"""
Data migration: seed 3 starter blog articles for Tamil Nadu job seekers.
"""
from django.db import migrations
from django.utils.text import slugify


ARTICLES = [
    {
        'title': 'Top 10 Fresher Interview Tips for Tamil Nadu Job Seekers',
        'category': 'interview-tips',
        'excerpt': 'Landing your first job in Tamil Nadu? Here are ten proven tips to help you ace the interview, from preparation to follow-up.',
        'body': (
            "Getting your first job can feel overwhelming, but the right preparation makes all the difference.\n\n"
            "1. Research the company before the interview — know their products, mission, and recent news.\n\n"
            "2. Practice common HR questions like 'Tell me about yourself' and 'Where do you see yourself in 5 years?'\n\n"
            "3. Dress professionally. For office roles in Chennai or Coimbatore, business casual is usually the right choice.\n\n"
            "4. Arrive 10 minutes early. Traffic in Tamil Nadu cities can be unpredictable — plan accordingly.\n\n"
            "5. Carry multiple copies of your resume and a folder with academic certificates.\n\n"
            "6. Prepare two or three thoughtful questions to ask the interviewer — it shows genuine interest.\n\n"
            "7. Be honest about your skills. Freshers are hired for potential, not perfection.\n\n"
            "8. Follow up with a brief thank-you email within 24 hours of the interview.\n\n"
            "9. Use the FirstHope AI Coach to practise mock interviews anytime before your big day.\n\n"
            "10. Stay positive. Rejections are part of the journey — every interview is practice for the next one."
        ),
    },
    {
        'title': 'How to Write a Strong Resume for Entry-Level Jobs in Tamil Nadu',
        'category': 'resume-tips',
        'excerpt': 'A well-crafted resume is your first impression. Learn how to structure a resume that gets noticed by Tamil Nadu employers.',
        'body': (
            "Your resume is the first thing a recruiter sees. Make every line count.\n\n"
            "Start with a clear header — your full name, email, phone number, and LinkedIn or GitHub link if relevant.\n\n"
            "Write a two-to-three sentence objective that is specific to the role you are applying for. Avoid generic statements.\n\n"
            "List your education with your degree, institution, year of passing, and CGPA (if above 7.0).\n\n"
            "Create a Skills section with the technologies you actually know. For IT roles, list programming languages, frameworks, and tools.\n\n"
            "Include any projects — college projects, personal projects, or internships. Describe what you built and what impact it had.\n\n"
            "Certifications matter. Add any NPTEL, Coursera, or vendor certifications you have completed.\n\n"
            "Keep the resume to one page for freshers. Recruiters spend an average of 7 seconds on an initial scan.\n\n"
            "Proofread carefully. A single spelling error can disqualify you at competitive companies.\n\n"
            "Use FirstHope to apply directly — your profile doubles as a digital resume that recruiters can review instantly."
        ),
    },
    {
        'title': 'Salary Guide 2026: Entry-Level Salaries in Tamil Nadu by Sector',
        'category': 'salary-guide',
        'excerpt': 'Wondering what to expect as a fresher salary in Tamil Nadu? This guide covers IT, manufacturing, banking, and more.',
        'body': (
            "Understanding typical salary ranges helps you negotiate confidently and set realistic expectations.\n\n"
            "IT & Software (Chennai): ₹3.5–6 LPA for freshers with a B.E./B.Tech. Skills in Python, Java, or cloud platforms can command higher offers.\n\n"
            "IT Services & BPO: ₹2.5–4 LPA. Entry roles often include voice and non-voice process associates.\n\n"
            "Manufacturing (Coimbatore, Hosur, Ambattur): ₹2–3.5 LPA for diploma and B.E. Mechanical/Electrical freshers.\n\n"
            "Banking & Finance (PSU): ₹3–4 LPA for IBPS clerks and PO positions after probation.\n\n"
            "Private Banks & NBFCs: ₹2.5–4 LPA. Sales and relationship manager roles often include performance-linked bonuses.\n\n"
            "Healthcare & Pharma: ₹2–3.5 LPA for lab technicians and junior medical representatives.\n\n"
            "Tips for negotiating: Always ask about the CTC breakdown — PF, insurance, and variable pay matter. Compare net take-home, not just CTC.\n\n"
            "Browse verified jobs on FirstHope to find roles with transparent salary disclosures across Tamil Nadu."
        ),
    },
]


def add_articles(apps, schema_editor):
    Article = apps.get_model('blog', 'Article')
    for data in ARTICLES:
        if not Article.objects.filter(slug=slugify(data['title'])).exists():
            Article.objects.create(
                title=data['title'],
                slug=slugify(data['title']),
                category=data['category'],
                excerpt=data['excerpt'],
                body=data['body'],
                is_published=True,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_articles, migrations.RunPython.noop),
    ]
