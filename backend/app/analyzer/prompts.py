"""Load + render markdown prompt templates from /prompts.

Prompts split into:
- system part (first paragraph after `# System` heading)
- user template (after `# User` heading), with `{{VAR}}` placeholders.

D17: optional locale suffix. We look for ``<name>.<lang>.md`` first, falling
back to ``<name>.md`` so existing single-file prompts keep working.
``lang`` accepts:
- ``"en"`` / ``"zh"``                                       -> exact match
- ``"auto"`` (default) + a sample text                      -> sniff with
  :func:`detect_lang`
- ``None``                                                  -> base file only
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from app.core.config import BASE_DIR

PROMPTS_DIR = BASE_DIR.parent / "prompts"

_SYSTEM_RE = re.compile(r"#\s*System\s*\n(.*?)(?=\n#\s|\Z)", re.DOTALL | re.IGNORECASE)
_USER_RE = re.compile(r"#\s*User\s*\n(.*?)\Z", re.DOTALL | re.IGNORECASE)
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def detect_lang(text: str) -> str:
    """Return ``"zh"`` if more than 10% of the chars are CJK, else ``"en"``.
    Used to pick a localised prompt when callers pass ``lang="auto"``.
    """
    if not text:
        return "en"
    cjk = len(_CJK_RE.findall(text))
    return "zh" if cjk * 10 >= max(1, len(text)) else "en"


def _resolve_path(name: str, lang: str | None) -> Path:
    """Pick a file in priority order: <name>.<lang>.md  ->  <name>.md."""
    if lang and lang != "auto":
        candidate = PROMPTS_DIR / f"{name}.{lang}.md"
        if candidate.exists():
            return candidate
    fallback = PROMPTS_DIR / f"{name}.md"
    if fallback.exists():
        return fallback
    # Last-resort: any .md starting with the name.
    matches = sorted(PROMPTS_DIR.glob(f"{name}*.md"))
    if matches:
        return matches[0]
    raise FileNotFoundError(f"prompt not found: {name} (lang={lang})")


@lru_cache(maxsize=64)
def load_prompt(name: str, lang: str | None = None) -> tuple[str, str]:
    """Return (system, user_template) for prompts/<name>[.lang].md."""
    path = _resolve_path(name, lang)
    raw = path.read_text(encoding="utf-8")

    # Strip YAML frontmatter
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            raw = parts[2]

    sys_m = _SYSTEM_RE.search(raw)
    usr_m = _USER_RE.search(raw)
    system = (sys_m.group(1) if sys_m else "").strip()
    user = (usr_m.group(1) if usr_m else raw).strip()
    return system, user


def render(template: str, **vars: str) -> str:
    out = template
    for k, v in vars.items():
        out = out.replace("{{" + k + "}}", v)
    return out
