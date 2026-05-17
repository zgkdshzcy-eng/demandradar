"""Lightweight text cleaning + language detection + keyword filters.

Heavy NLP is intentionally avoided in the collector path - we want
collection to be I/O-bound and cheap. Heavy lifting moves to the analyzer.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

from app.core.config import BASE_DIR

DATA_DIR = BASE_DIR.parent / "data"

_URL_RE = re.compile(r"https?://\S+")
_WHITESPACE_RE = re.compile(r"\s+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def detect_lang(text: str) -> str:
    """Cheap heuristic: any CJK char => 'zh', else 'en' (or 'unknown' if empty)."""
    if not text or not text.strip():
        return "unknown"
    if _CJK_RE.search(text):
        return "zh"
    return "en"


def normalize(text: str) -> str:
    """Strip URLs, collapse whitespace, trim. Keep semantics, ignore styling."""
    if not text:
        return ""
    t = _URL_RE.sub(" ", text)
    t = _WHITESPACE_RE.sub(" ", t).strip()
    return t


@lru_cache(maxsize=1)
def _seed_keywords() -> dict[str, dict[str, list[str]]]:
    p = DATA_DIR / "seed_keywords.yaml"
    if not p.exists():
        return {"zh": {"strong": [], "medium": []}, "en": {"strong": [], "medium": []}, "blocklist": []}
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def is_blocked(text: str) -> bool:
    """True if text contains any blocklist term (case-insensitive)."""
    if not text:
        return False
    lower = text.lower()
    return any(term.lower() in lower for term in _seed_keywords().get("blocklist", []))


def signal_strength(text: str, lang: str) -> str:
    """Return 'strong' | 'medium' | 'weak' based on seed keyword matches."""
    if not text:
        return "weak"
    kws = _seed_keywords().get(lang, {})
    lower = text.lower()
    if any(kw.lower() in lower for kw in kws.get("strong", [])):
        return "strong"
    if any(kw.lower() in lower for kw in kws.get("medium", [])):
        return "medium"
    return "weak"


def clean_payload(text: str) -> tuple[str, str, bool]:
    """Convenience: returns (normalized_text, lang, is_blocked)."""
    norm = normalize(text)
    lang = detect_lang(norm)
    return norm, lang, is_blocked(norm)
