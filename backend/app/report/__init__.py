"""Project brief & weekly report generators (Day 7-8)."""
from app.report.pdf import (
    PDF_AVAILABLE,
    md_to_html_doc,
    md_to_html_fragment,
    md_to_pdf_bytes,
)
from app.report.project_brief import BriefStats, generate_one, run_briefs
from app.report.weekly import WeeklyStats, generate_weekly

__all__ = [
    "BriefStats",
    "PDF_AVAILABLE",
    "WeeklyStats",
    "generate_one",
    "generate_weekly",
    "md_to_html_doc",
    "md_to_html_fragment",
    "md_to_pdf_bytes",
    "run_briefs",
]
