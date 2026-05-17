"""Markdown -> HTML -> PDF rendering with optional weasyprint.

Markdown -> HTML always works (uses python-markdown). PDF requires weasyprint
which has native dependencies (GTK on Windows). We try-import; if it fails,
HTML download still works and PDF endpoint returns 503.
"""
from __future__ import annotations

from typing import Any

import markdown as md

PDF_AVAILABLE: bool
_HTML2PDF: Any | None

try:
    from weasyprint import HTML as _HTML  # type: ignore[import-not-found]
    PDF_AVAILABLE = True
    _HTML2PDF = _HTML
except Exception:  # noqa: BLE001
    PDF_AVAILABLE = False
    _HTML2PDF = None


_BASE_CSS = """
body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
       max-width: 760px; margin: 40px auto; padding: 0 20px; line-height: 1.7;
       color: #111; }
h1, h2, h3 { line-height: 1.3; margin-top: 1.6em; }
h1 { border-bottom: 1px solid #ddd; padding-bottom: .3em; }
h2 { color: #0369a1; }
code { background: #f4f4f5; padding: 1px 5px; border-radius: 3px; font-size: 0.95em; }
pre { background: #0f172a; color: #e2e8f0; padding: 12px 14px; border-radius: 6px;
      overflow-x: auto; }
pre code { background: transparent; color: inherit; padding: 0; }
blockquote { border-left: 3px solid #0ea5e9; margin: 0; padding: .2em 1em; color: #475569; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #e5e7eb; padding: 6px 10px; text-align: left; }
a { color: #0369a1; }
"""


def md_to_html_fragment(markdown: str) -> str:
    """Markdown -> HTML body fragment (no <html>/<head>)."""
    return md.markdown(
        markdown,
        extensions=["extra", "sane_lists", "tables", "fenced_code", "toc"],
        output_format="html5",
    )


def md_to_html_doc(markdown: str, *, title: str = "Project Brief") -> str:
    """Full standalone HTML document with embedded base CSS."""
    body = md_to_html_fragment(markdown)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>{_escape(title)}</title>
<style>{_BASE_CSS}</style>
</head>
<body>
{body}
</body>
</html>"""


def md_to_pdf_bytes(markdown: str, *, title: str = "Project Brief") -> bytes:
    """Render markdown to PDF bytes. Raises RuntimeError if weasyprint missing."""
    if not PDF_AVAILABLE or _HTML2PDF is None:
        raise RuntimeError(
            "PDF rendering unavailable: install with `pip install -e \".[pdf]\"` "
            "(weasyprint requires GTK on Windows)."
        )
    html = md_to_html_doc(markdown, title=title)
    return _HTML2PDF(string=html).write_pdf()  # type: ignore[no-any-return]


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
