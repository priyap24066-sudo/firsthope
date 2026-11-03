import re


def calculate_skill_match(job_skills, candidate_skills):
    def split_skills(skills):
        return [skill.strip() for skill in re.split(r'[,\s]+', skills or '') if skill.strip()]

    required_skills = []
    seen_required = set()
    for skill in split_skills(job_skills):
        normalized = skill.casefold()
        if normalized not in seen_required:
            required_skills.append(skill)
            seen_required.add(normalized)

    candidate_skill_set = {
        skill.casefold()
        for skill in split_skills(candidate_skills)
    }
    matched_skills = [
        skill for skill in required_skills
        if skill.casefold() in candidate_skill_set
    ]
    missing_skills = [
        skill for skill in required_skills
        if skill.casefold() not in candidate_skill_set
    ]
    percentage = round(len(matched_skills) / len(required_skills) * 100) if required_skills else 0

    return {
        'percentage': percentage,
        'ring_offset': round(220 * (1 - percentage / 100)),
        'matched_skills': matched_skills,
        'missing_skills': missing_skills,
        'has_candidate_skills': bool(candidate_skill_set),
    }
