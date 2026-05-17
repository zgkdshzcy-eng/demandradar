"""Sanity coverage for D18 (English-first / bilingual rollout).

Three layers under test:

1. ``app.core.locale.pick_locale`` — Accept-Language parsing + explicit hint.
2. ``app.core.email_templates`` — every transactional email composer must
   render English by default and Chinese when explicitly asked.
3. ``app.notify.twitter._compose_weekly_tweet`` — defaults to English copy.

These tests intentionally avoid SMTP / database / network calls so they run
in <50 ms and are robust on Windows agents.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.core import locale as loc_mod
from app.core.email_templates import (
    login_welcome,
    paid_confirmation,
    referral_bonus,
    waitlist_welcome,
)
from app.notify.twitter import _compose_weekly_tweet


# ---------------- locale helper ----------------

def test_pick_locale_explicit_wins_over_header() -> None:
    assert (
        loc_mod.pick_locale(explicit="zh", header="en-US,en;q=0.9")
        == "zh"
    )


def test_pick_locale_falls_back_to_accept_language() -> None:
    assert (
        loc_mod.pick_locale(explicit=None, header="zh-CN,zh;q=0.9,en;q=0.8")
        == "zh"
    )


def test_pick_locale_unsupported_explicit_drops_to_header() -> None:
    # `de` isn't supported -> we should still match the EN tag in the header.
    assert (
        loc_mod.pick_locale(explicit="de", header="de-DE,de;q=0.9,en;q=0.5")
        == "en"
    )


def test_pick_locale_default_is_english() -> None:
    assert loc_mod.pick_locale() == "en"


def test_stored_or_normalises_unsupported() -> None:
    assert loc_mod.stored_or("en", "fr") == "en"
    assert loc_mod.stored_or("en", "zh") == "zh"
    assert loc_mod.stored_or("en", None) == "en"


# ---------------- email templates ----------------

def test_waitlist_welcome_default_is_english() -> None:
    subj, text, html = waitlist_welcome("alice@example.com")
    assert "waitlist" in subj.lower()
    assert "Welcome to the waitlist" in html
    assert "Live radar" in text
    assert "候补" not in text  # no Chinese leakage


def test_waitlist_welcome_chinese() -> None:
    subj, text, html = waitlist_welcome("bob@example.com", locale="zh")
    assert "候补" in subj
    assert "实时雷达" in text
    assert "Welcome to the waitlist" not in html


def test_login_welcome_referral_block_in_english() -> None:
    subj, text, html = login_welcome(
        "carol@example.com", referral_url="https://x.test/?ref=AB12"
    )
    assert "signed in" in subj.lower()
    assert "referral link" in text.lower()
    assert "https://x.test/?ref=AB12" in text
    assert "推荐链接" not in html


def test_paid_confirmation_english_uses_amount_label() -> None:
    subj, text, html = paid_confirmation(
        "dave@example.com",
        plan="weekly_pro",
        amount_cents=990,
        currency="usd",
        brief_id=None,
    )
    assert "Payment received" in subj
    assert "Amount" in text
    assert "9.90 USD" in text
    assert "金额" not in html


def test_paid_confirmation_chinese_keeps_amount_in_local_label() -> None:
    subj, text, html = paid_confirmation(
        "ed@example.com",
        plan="brief_oneoff",
        amount_cents=2900,
        currency="usd",
        brief_id=42,
        locale="zh",
    )
    assert "已收到付款" in subj
    assert "金额" in text
    assert "/briefs/42" in text


def test_referral_bonus_english() -> None:
    subj, text, html = referral_bonus(
        "fiona@example.com",
        referred_email="newbie@example.com",
        bonus_days=7,
    )
    assert "+7 days" in subj
    assert "extended your Pro subscription by 7 days" in text
    assert "推荐生效" not in html


# ---------------- tweet composer ----------------

@dataclass
class _PP:
    pain: str | None
    target_user: str | None
    total_score: float | None


@dataclass
class _Report:
    issue_no: int


def test_tweet_default_is_english_no_top() -> None:
    out = _compose_weekly_tweet(_Report(issue_no=3), top=None)
    assert "weekly #3" in out
    assert "indie hackers" in out
    assert "公开数据源" not in out


def test_tweet_default_is_english_with_top() -> None:
    pp = _PP(
        pain="Notion is too slow in some regions",
        target_user="remote knowledge workers",
        total_score=86.0,
    )
    out = _compose_weekly_tweet(_Report(issue_no=4), top=pp)
    assert "this week's #1 pain" in out
    assert "Target: remote knowledge workers" in out
    assert "score 86" in out
    assert len(out) <= 280


def test_tweet_chinese_when_requested() -> None:
    pp = _PP(pain="Notion 国内访问慢", target_user="远程办公", total_score=86.0)
    out = _compose_weekly_tweet(_Report(issue_no=5), top=pp, locale="zh")
    assert "本周 #1 痛点" in out
    assert "目标：远程办公" in out
    assert len(out) <= 280


def test_tweet_truncates_long_pain_within_limit() -> None:
    pp = _PP(
        pain="really long pain " * 30,  # ~510 chars
        target_user="indie devs",
        total_score=70.0,
    )
    out = _compose_weekly_tweet(_Report(issue_no=6), top=pp)
    assert len(out) <= 280
    assert "this week's #1 pain" in out


# ---------------- newsletter render path ----------------

def test_newsletter_render_english_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_render` builds the email body bilingually based on the locale arg."""
    from app.notify import newsletter

    @dataclass
    class _Issue:
        issue_no: int = 1
        title: str | None = None
        markdown_preview: str = "# DemandRadar\n- top pain"

    subj, text, html = newsletter._render(
        report=_Issue(),  # type: ignore[arg-type]
        email="reader@example.com",
        kind="user",
        locale="en",
    )
    assert "[DemandRadar]" in subj
    assert "DemandRadar weekly #1" in subj
    assert "Read the full sample" in html
    assert "Unsubscribe" in text
    assert "在线阅读" not in text


def test_newsletter_render_chinese() -> None:
    from app.notify import newsletter

    @dataclass
    class _Issue:
        issue_no: int = 2
        title: str | None = None
        markdown_preview: str = "# 周报\n- top"

    subj, text, html = newsletter._render(
        report=_Issue(),  # type: ignore[arg-type]
        email="reader@example.com",
        kind="user",
        locale="zh",
    )
    assert "DemandRadar 周报 #2" in subj
    assert "在线阅读样刊" in text
    assert "Unsubscribe" not in html
