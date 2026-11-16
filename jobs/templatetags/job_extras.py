"""
Custom template tags and filters for the jobs app.
"""
import re

from django import template

register = template.Library()


# ── Salary formatter ──────────────────────────────────────────────────────────

_LAKH_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*[-–to]+\s*(\d+(?:\.\d+)?)\s*(?:l(?:akhs?)?|lpa)',
    re.IGNORECASE,
)
_SINGLE_LAKH_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*(?:l(?:akhs?)?|lpa)',
    re.IGNORECASE,
)
_MONTH_RE = re.compile(
    r'(\d[\d,]*)\s*(?:/-|per\s*month|/month|pm|month)',
    re.IGNORECASE,
)
_RANGE_MONTH_RE = re.compile(
    r'(\d[\d,]*)\s*[-–to]+\s*(\d[\d,]*)\s*(?:/-|per\s*month|/month|pm|month)',
    re.IGNORECASE,
)


@register.filter
def format_salary(value):
    """
    Normalise a free-text salary string into a readable INR format.

    Examples:
        '3-5 LPA'          → '₹3–5 LPA'
        '8000/month'        → '₹8,000/month'
        '12000 - 18000 pm' → '₹12,000–₹18,000/month'
        '50000'            → '₹50,000'
        ''                 → 'Salary not disclosed'
    """
    if not value:
        return 'Salary not disclosed'

    text = str(value).strip()

    # Range in lakhs: "3-5 LPA", "3 to 5 lakhs"
    m = _LAKH_RE.search(text)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        lo_s = f'{lo:g}'
        hi_s = f'{hi:g}'
        return f'₹{lo_s}–{hi_s} LPA'

    # Single lakh: "5 LPA", "5 lakhs"
    m = _SINGLE_LAKH_RE.search(text)
    if m:
        val = float(m.group(1))
        return f'₹{val:g} LPA'

    # Range in monthly: "8000-12000/month"
    m = _RANGE_MONTH_RE.search(text)
    if m:
        lo = int(m.group(1).replace(',', ''))
        hi = int(m.group(2).replace(',', ''))
        return f'₹{lo:,}–₹{hi:,}/month'

    # Single monthly: "8000/month"
    m = _MONTH_RE.search(text)
    if m:
        val = int(m.group(1).replace(',', ''))
        return f'₹{val:,}/month'

    # Bare number → assume annual in INR
    bare = re.sub(r'[^\d]', '', text)
    if bare:
        val = int(bare)
        if val >= 100000:
            lpa = val / 100000
            return f'₹{lpa:g} LPA'
        return f'₹{val:,}'

    # Fallback: return as-is
    return text
