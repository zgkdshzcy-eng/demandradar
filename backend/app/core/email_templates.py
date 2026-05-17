"""Transactional email templates (bilingual).

Each function returns ``(subject, text, html)`` and accepts a ``locale``
keyword (``"en"`` | ``"zh"``), defaulting to English post-pivot. The
copy lives inline (no Jinja files) so contributors can grep it.

All emails should:
- be short (< 200 words)
- have a plain-text version
- use absolute URLs (PUBLIC_BASE_URL)
- never contain secrets
"""
from __future__ import annotations

from app.core.config import settings
from app.core.locale import DEFAULT_LOCALE, SUPPORTED


def _base_url() -> str:
    return settings.public_base_url.rstrip("/") or "https://demandradar.example.com"


def _resolve(locale: str | None) -> str:
    if locale and locale in SUPPORTED:
        return locale
    return DEFAULT_LOCALE


def _wrap_html(body: str, *, title: str, locale: str) -> str:
    lang_attr = "zh-CN" if locale == "zh" else "en"
    footer = (
        "你收到这封邮件，是因为在 DemandRadar 留下了邮箱。回复邮件即可联系我们。"
        if locale == "zh"
        else "You're receiving this because you signed up at DemandRadar. Reply to unsubscribe."
    )
    base = _base_url()
    return f"""<!doctype html>
<html lang="{lang_attr}"><head><meta charset="utf-8"><title>{title}</title></head>
<body style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;background:#f6f7fb;padding:24px;color:#111;">
<div style="max-width:560px;margin:0 auto;background:#fff;border-radius:12px;padding:28px 32px;box-shadow:0 2px 8px rgba(0,0,0,.04);">
{body}
<hr style="border:0;border-top:1px solid #eee;margin:24px 0;">
<p style="font-size:12px;color:#888;">
DemandRadar &middot; <a href="{base}" style="color:#888;">{base}</a><br>
{footer}
</p>
</div></body></html>"""


# ---------- 1. Waitlist welcome ----------

def waitlist_welcome(email: str, *, locale: str = DEFAULT_LOCALE) -> tuple[str, str, str]:
    locale = _resolve(locale)
    base = _base_url()
    if locale == "zh":
        subject = "[DemandRadar] 已收到候补，下一期周报会先送你"
        text = (
            f"Hi,\n\n"
            f"我们已经收到 {email} 的候补申请。下一期周报上线时会先发到你邮箱。\n\n"
            f"在等待期间，你可以先看：\n"
            f"- 实时雷达 Top 20：{base}/radar\n"
            f"- 上一期样刊：{base}/sample\n"
            f"- 项目书示例：{base}/briefs\n\n"
            f"任何反馈直接回这封邮件即可。\n"
        )
        html_title = "DemandRadar · 候补已收到"
        html = _wrap_html(
            f"<h2 style='margin-top:0'>欢迎加入候补名单 👋</h2>"
            f"<p>我们已经收到 <b>{email}</b> 的候补申请。下一期周报上线时会第一时间发到你邮箱。</p>"
            f"<p>在等待期间可以先看：</p>"
            f"<ul>"
            f"<li><a href='{base}/radar'>实时雷达 Top 20</a></li>"
            f"<li><a href='{base}/sample'>上一期样刊</a></li>"
            f"<li><a href='{base}/briefs'>项目书示例</a></li>"
            f"</ul>"
            f"<p>任何反馈直接回这封邮件即可。</p>",
            title=html_title,
            locale=locale,
        )
        return subject, text, html

    # English (default)
    subject = "[DemandRadar] You're on the waitlist"
    text = (
        f"Hi,\n\n"
        f"We received your sign-up for {email}. The next weekly issue lands in your inbox the moment it ships.\n\n"
        f"While you wait, take a look at:\n"
        f"- Live radar (Top 20 pain points): {base}/radar\n"
        f"- Latest sample issue: {base}/sample\n"
        f"- Project briefs: {base}/briefs\n\n"
        f"Reply to this email any time — we read every message.\n"
    )
    html_title = "DemandRadar · Welcome"
    html = _wrap_html(
        f"<h2 style='margin-top:0'>Welcome to the waitlist 👋</h2>"
        f"<p>We received your sign-up for <b>{email}</b>. The next weekly issue lands in your inbox the moment it ships.</p>"
        f"<p>While you wait, take a look at:</p>"
        f"<ul>"
        f"<li><a href='{base}/radar'>Live radar — Top 20 pain points</a></li>"
        f"<li><a href='{base}/sample'>Latest sample issue</a></li>"
        f"<li><a href='{base}/briefs'>Project briefs</a></li>"
        f"</ul>"
        f"<p>Reply to this email any time — we read every message.</p>",
        title=html_title,
        locale=locale,
    )
    return subject, text, html


# ---------- 2. First successful login ----------

def login_welcome(
    email: str,
    referral_url: str | None = None,
    *,
    locale: str = DEFAULT_LOCALE,
) -> tuple[str, str, str]:
    locale = _resolve(locale)
    base = _base_url()
    if locale == "zh":
        ref_block_text = (
            f"\n推荐链接（每位朋友通过你的链接付费，你获得 7 天 Pro）：\n{referral_url}\n"
            if referral_url
            else ""
        )
        ref_block_html = (
            f"<p>推荐链接 — 每位朋友通过你的链接付费，你获得 <b>7 天 Pro</b>：</p>"
            f"<p style='word-break:break-all;background:#f3f4f6;padding:10px;border-radius:6px;font-size:13px;'>"
            f"<a href='{referral_url}'>{referral_url}</a></p>"
            if referral_url
            else ""
        )
        subject = "[DemandRadar] 账户已激活"
        text = (
            f"Hi,\n\n"
            f"账户 {email} 已成功登录 DemandRadar。\n\n"
            f"快速链接：\n"
            f"- 账户中心：{base}/account\n"
            f"- 实时雷达：{base}/radar\n"
            f"- 定价：{base}/pricing\n"
            f"{ref_block_text}\n"
            f"如果不是你本人，请直接回复这封邮件告诉我们。\n"
        )
        html = _wrap_html(
            f"<h2 style='margin-top:0'>账户已激活 ✨</h2>"
            f"<p>账户 <b>{email}</b> 已成功登录 DemandRadar。</p>"
            f"<p>快速链接：</p>"
            f"<ul>"
            f"<li><a href='{base}/account'>账户中心</a></li>"
            f"<li><a href='{base}/radar'>实时雷达</a></li>"
            f"<li><a href='{base}/pricing'>定价</a></li>"
            f"</ul>"
            f"{ref_block_html}"
            f"<p style='color:#888;font-size:13px;'>如果不是你本人，请直接回复这封邮件告诉我们。</p>",
            title="DemandRadar · 已登录",
            locale=locale,
        )
        return subject, text, html

    # English
    ref_block_text = (
        f"\nYour referral link (each friend who pays via this link earns you 7 free days of Pro):\n{referral_url}\n"
        if referral_url
        else ""
    )
    ref_block_html = (
        f"<p>Your referral link — each friend who pays via this link earns you <b>7 free days of Pro</b>:</p>"
        f"<p style='word-break:break-all;background:#f3f4f6;padding:10px;border-radius:6px;font-size:13px;'>"
        f"<a href='{referral_url}'>{referral_url}</a></p>"
        if referral_url
        else ""
    )
    subject = "[DemandRadar] You're signed in"
    text = (
        f"Hi,\n\n"
        f"You just signed in to DemandRadar with {email}.\n\n"
        f"Quick links:\n"
        f"- Account center: {base}/account\n"
        f"- Live radar: {base}/radar\n"
        f"- Pricing: {base}/pricing\n"
        f"{ref_block_text}\n"
        f"If this wasn't you, just reply to this email and we'll lock the account.\n"
    )
    html = _wrap_html(
        f"<h2 style='margin-top:0'>You're signed in ✨</h2>"
        f"<p>You just signed in to DemandRadar with <b>{email}</b>.</p>"
        f"<p>Quick links:</p>"
        f"<ul>"
        f"<li><a href='{base}/account'>Account center</a></li>"
        f"<li><a href='{base}/radar'>Live radar</a></li>"
        f"<li><a href='{base}/pricing'>Pricing</a></li>"
        f"</ul>"
        f"{ref_block_html}"
        f"<p style='color:#888;font-size:13px;'>If this wasn't you, just reply to this email and we'll lock the account.</p>",
        title="DemandRadar · Signed in",
        locale=locale,
    )
    return subject, text, html


# ---------- 3. Paid checkout confirmation ----------

PLAN_DISPLAY: dict[str, dict[str, str]] = {
    "weekly_pro": {"en": "Pro Weekly subscription", "zh": "Pro 周报订阅"},
    "studio": {"en": "Studio subscription", "zh": "Studio 订阅"},
    "brief_oneoff": {"en": "Single project brief", "zh": "单份项目书"},
}


def _plan_display(plan: str, locale: str) -> str:
    entry = PLAN_DISPLAY.get(plan)
    if entry:
        return entry.get(locale) or entry.get("en") or plan
    return plan


def paid_confirmation(
    email: str,
    *,
    plan: str,
    amount_cents: int | None,
    currency: str | None,
    brief_id: int | None,
    locale: str = DEFAULT_LOCALE,
) -> tuple[str, str, str]:
    locale = _resolve(locale)
    base = _base_url()
    title = _plan_display(plan, locale)
    amt_str = ""
    if amount_cents and currency:
        if locale == "zh":
            amt_str = f"  金额: {amount_cents/100:.2f} {currency.upper()}"
        else:
            amt_str = f"  Amount: {amount_cents/100:.2f} {currency.upper()}"
    if locale == "zh":
        brief_link = f"\n  项目书: {base}/briefs/{brief_id}" if brief_id else ""
        subject = f"[DemandRadar] 已收到付款 · {title}"
        text = (
            f"Hi,\n\n"
            f"我们已收到你的付款，{title} 已激活。\n"
            f"  邮箱: {email}\n"
            f"  套餐: {title} ({plan}){amt_str}{brief_link}\n\n"
            f"账户中心查看订阅与发票：{base}/account\n"
            f"\n如对账单有疑问，直接回复这封邮件，工作日 24h 内响应。\n"
        )
        html = _wrap_html(
            f"<h2 style='margin-top:0'>付款成功 ✅</h2>"
            f"<p>我们已收到你的付款，<b>{title}</b> 已激活。</p>"
            f"<table style='font-size:14px;color:#444;'>"
            f"<tr><td style='padding:4px 12px 4px 0;color:#888;'>邮箱</td><td>{email}</td></tr>"
            f"<tr><td style='padding:4px 12px 4px 0;color:#888;'>套餐</td><td>{title} ({plan})</td></tr>"
            + (
                f"<tr><td style='padding:4px 12px 4px 0;color:#888;'>金额</td><td>{amount_cents/100:.2f} {currency.upper()}</td></tr>"
                if amount_cents and currency else ""
            )
            + (
                f"<tr><td style='padding:4px 12px 4px 0;color:#888;'>项目书</td><td><a href='{base}/briefs/{brief_id}'>查看</a></td></tr>"
                if brief_id else ""
            )
            + f"</table>"
            f"<p style='margin-top:18px;'><a href='{base}/account' style='display:inline-block;background:#3b82f6;color:#fff;padding:8px 16px;border-radius:6px;text-decoration:none;'>进入账户中心</a></p>"
            f"<p style='color:#888;font-size:13px;'>如对账单有疑问，直接回复这封邮件，工作日 24h 内响应。</p>",
            title="DemandRadar · 付款成功",
            locale=locale,
        )
        return subject, text, html

    # English
    brief_link = f"\n  Brief: {base}/briefs/{brief_id}" if brief_id else ""
    subject = f"[DemandRadar] Payment received · {title}"
    text = (
        f"Hi,\n\n"
        f"We received your payment — your {title} is now active.\n"
        f"  Email: {email}\n"
        f"  Plan:  {title} ({plan}){amt_str}{brief_link}\n\n"
        f"Manage your subscription and invoices: {base}/account\n"
        f"\nQuestions about the receipt? Reply to this email — we respond within one business day.\n"
    )
    html = _wrap_html(
        f"<h2 style='margin-top:0'>Payment received ✅</h2>"
        f"<p>We received your payment — your <b>{title}</b> is now active.</p>"
        f"<table style='font-size:14px;color:#444;'>"
        f"<tr><td style='padding:4px 12px 4px 0;color:#888;'>Email</td><td>{email}</td></tr>"
        f"<tr><td style='padding:4px 12px 4px 0;color:#888;'>Plan</td><td>{title} ({plan})</td></tr>"
        + (
            f"<tr><td style='padding:4px 12px 4px 0;color:#888;'>Amount</td><td>{amount_cents/100:.2f} {currency.upper()}</td></tr>"
            if amount_cents and currency else ""
        )
        + (
            f"<tr><td style='padding:4px 12px 4px 0;color:#888;'>Brief</td><td><a href='{base}/briefs/{brief_id}'>open</a></td></tr>"
            if brief_id else ""
        )
        + f"</table>"
        f"<p style='margin-top:18px;'><a href='{base}/account' style='display:inline-block;background:#3b82f6;color:#fff;padding:8px 16px;border-radius:6px;text-decoration:none;'>Open account center</a></p>"
        f"<p style='color:#888;font-size:13px;'>Questions about the receipt? Reply to this email — we respond within one business day.</p>",
        title="DemandRadar · Payment received",
        locale=locale,
    )
    return subject, text, html


# ---------- 4. Referral bonus granted (to referrer) ----------

def referral_bonus(
    referrer_email: str,
    *,
    referred_email: str,
    bonus_days: int,
    locale: str = DEFAULT_LOCALE,
) -> tuple[str, str, str]:
    locale = _resolve(locale)
    base = _base_url()
    if locale == "zh":
        subject = f"[DemandRadar] 你的推荐生效，已赠 {bonus_days} 天 Pro"
        text = (
            f"Hi,\n\n"
            f"好消息：{referred_email} 通过你的推荐链接完成了首次付费，"
            f"已为你延长 {bonus_days} 天 Pro 订阅期 🎁\n\n"
            f"在账户中心查看到期日：{base}/account\n"
            f"继续邀请朋友：{base}/account（点击 \"复制推荐链接\"）\n"
        )
        html = _wrap_html(
            f"<h2 style='margin-top:0'>推荐生效 🎁</h2>"
            f"<p><b>{referred_email}</b> 通过你的推荐链接完成了首次付费，"
            f"已为你延长 <b>{bonus_days} 天</b> Pro 订阅期。</p>"
            f"<p><a href='{base}/account' style='display:inline-block;background:#10b981;color:#fff;padding:8px 16px;border-radius:6px;text-decoration:none;'>查看到期日</a></p>",
            title="DemandRadar · 推荐生效",
            locale=locale,
        )
        return subject, text, html

    # English
    subject = f"[DemandRadar] Your referral landed — +{bonus_days} days of Pro"
    text = (
        f"Hi,\n\n"
        f"Good news: {referred_email} just paid via your referral link. "
        f"We've extended your Pro subscription by {bonus_days} days 🎁\n\n"
        f"Check your new expiry in the account center: {base}/account\n"
        f"Keep inviting friends — copy your referral link from {base}/account.\n"
    )
    html = _wrap_html(
        f"<h2 style='margin-top:0'>Your referral landed 🎁</h2>"
        f"<p><b>{referred_email}</b> just paid via your referral link, so we've "
        f"extended your Pro subscription by <b>{bonus_days} days</b>.</p>"
        f"<p><a href='{base}/account' style='display:inline-block;background:#10b981;color:#fff;padding:8px 16px;border-radius:6px;text-decoration:none;'>Check new expiry</a></p>",
        title="DemandRadar · Referral landed",
        locale=locale,
    )
    return subject, text, html


# ---------- 5. Payment failed (dunning) ----------

def payment_failed(
    email: str,
    *,
    plan: str,
    portal_url: str | None = None,
    locale: str = DEFAULT_LOCALE,
) -> tuple[str, str, str]:
    """Sent when Stripe reports `invoice.payment_failed`. Asks the user to
    update their card via the customer portal before service is suspended."""
    locale = _resolve(locale)
    base = _base_url()
    title = _plan_display(plan, locale)
    portal = portal_url or f"{base}/account"
    if locale == "zh":
        subject = f"[DemandRadar] 续费失败，请尽快更新支付方式 · {title}"
        text = (
            "Hi,\n\n"
            f"我们刚刚尝试为你的 {title} 自动续费，但银行/卡组织拒绝了这笔扣款。\n\n"
            f"请在 {portal} 更新支付方式，订阅会在下次重试时自动恢复。\n\n"
            "如果你最近换了信用卡，最常见原因是旧卡过期。Stripe 会在接下来 4 天内"
            "自动重试 3 次；之后我们会暂停服务以避免继续扣款失败。\n"
        )
        html = _wrap_html(
            "<h2 style='margin-top:0'>续费失败 ⚠️</h2>"
            f"<p>我们刚刚尝试为你的 <b>{title}</b> 自动续费，但被银行拒绝。</p>"
            "<p>最常见原因：信用卡过期 / 余额不足 / 风控拦截。</p>"
            f"<p style='margin-top:18px;'><a href='{portal}' "
            "style='display:inline-block;background:#ef4444;color:#fff;"
            "padding:10px 18px;border-radius:6px;text-decoration:none;'>"
            "更新支付方式</a></p>"
            "<p style='color:#888;font-size:13px;'>Stripe 会在接下来 4 天内自动"
            "重试；如果仍未成功，我们会暂停服务以避免继续扣款失败。</p>",
            title="DemandRadar · 续费失败",
            locale=locale,
        )
        return subject, text, html

    subject = f"[DemandRadar] Payment failed — please update your card · {title}"
    text = (
        "Hi,\n\n"
        f"Stripe just tried to renew your {title} but the charge was declined "
        "by the issuing bank.\n\n"
        f"Update your payment method here: {portal}\n\n"
        "Stripe will retry up to three times over the next 4 days. If the "
        "card still fails we'll pause the subscription to avoid repeated "
        "decline fees.\n"
    )
    html = _wrap_html(
        "<h2 style='margin-top:0'>Payment failed ⚠️</h2>"
        f"<p>Stripe just tried to renew your <b>{title}</b> but the charge "
        "was declined by the issuing bank.</p>"
        "<p>Most common reasons: expired card, insufficient funds, or fraud "
        "block.</p>"
        f"<p style='margin-top:18px;'><a href='{portal}' "
        "style='display:inline-block;background:#ef4444;color:#fff;"
        "padding:10px 18px;border-radius:6px;text-decoration:none;'>"
        "Update payment method</a></p>"
        "<p style='color:#888;font-size:13px;'>Stripe will retry up to three "
        "times over the next 4 days. If the card still fails we'll pause the "
        "subscription.</p>",
        title="DemandRadar · Payment failed",
        locale=locale,
    )
    return subject, text, html


# ---------- 6. Cold-start re-engagement (Top 3 painpoints) ----------

def cold_start_top3(
    email: str,
    *,
    items: list[dict],
    locale: str = DEFAULT_LOCALE,
) -> tuple[str, str, str]:
    """Re-engagement email for users who signed up but didn't subscribe.

    `items` is a list of dicts with keys: `pain`, `target_user`, `score`,
    `pain_point_id`. Top 3 are rendered.
    """
    locale = _resolve(locale)
    base = _base_url()
    items = items[:3]

    if locale == "zh":
        subject = "[DemandRadar] 你可能错过的 3 个高付费意愿痛点"
        bullet_text = "\n".join(
            f"{i+1}. {it.get('pain','')} · score {it.get('score',0):.0f}"
            f"\n   目标：{it.get('target_user') or '—'}"
            f"\n   {base}/radar"
            for i, it in enumerate(items)
        )
        text = (
            "Hi,\n\n"
            "过去几天 DemandRadar 雷达上分数最高的 3 个痛点：\n\n"
            f"{bullet_text}\n\n"
            f"完整 Top 20：{base}/radar\n"
            f"订阅 Pro 周报每周收 20 条 + 高分项目书：{base}/pricing\n"
        )
        bullet_html = "".join(
            f"<li style='margin-bottom:14px;'>"
            f"<div style='font-weight:600;'>{it.get('pain','')}</div>"
            f"<div style='color:#666;font-size:13px;'>"
            f"score {it.get('score',0):.0f} · {it.get('target_user') or '—'}</div>"
            f"</li>"
            for it in items
        )
        html = _wrap_html(
            "<h2 style='margin-top:0'>3 个你可能错过的高分痛点 📡</h2>"
            "<p>过去几天 DemandRadar 雷达上分数最高的痛点：</p>"
            f"<ol style='padding-left:18px;'>{bullet_html}</ol>"
            f"<p><a href='{base}/radar' style='color:#3b82f6;'>查看完整 Top 20 →</a></p>"
            f"<p style='margin-top:18px;'><a href='{base}/pricing' "
            "style='display:inline-block;background:#3b82f6;color:#fff;"
            "padding:8px 16px;border-radius:6px;text-decoration:none;'>"
            "查看 Pro 周报订阅</a></p>",
            title="DemandRadar · Top 3",
            locale=locale,
        )
        return subject, text, html

    subject = "[DemandRadar] 3 high-WTP pain points you might have missed"
    bullet_text = "\n".join(
        f"{i+1}. {it.get('pain','')} · score {it.get('score',0):.0f}"
        f"\n   Target: {it.get('target_user') or '—'}"
        f"\n   {base}/radar"
        for i, it in enumerate(items)
    )
    text = (
        "Hi,\n\n"
        "Top 3 highest-scoring pain points on the DemandRadar feed in the "
        "past few days:\n\n"
        f"{bullet_text}\n\n"
        f"Full Top 20: {base}/radar\n"
        f"Subscribe to Pro Weekly to get 20 fresh ones + build-ready briefs "
        f"every week: {base}/pricing\n"
    )
    bullet_html = "".join(
        f"<li style='margin-bottom:14px;'>"
        f"<div style='font-weight:600;'>{it.get('pain','')}</div>"
        f"<div style='color:#666;font-size:13px;'>"
        f"score {it.get('score',0):.0f} · {it.get('target_user') or '—'}</div>"
        f"</li>"
        for it in items
    )
    html = _wrap_html(
        "<h2 style='margin-top:0'>3 high-WTP pain points you might have missed 📡</h2>"
        "<p>Top-scoring pain points on the DemandRadar feed in the past few days:</p>"
        f"<ol style='padding-left:18px;'>{bullet_html}</ol>"
        f"<p><a href='{base}/radar' style='color:#3b82f6;'>See the full Top 20 →</a></p>"
        f"<p style='margin-top:18px;'><a href='{base}/pricing' "
        "style='display:inline-block;background:#3b82f6;color:#fff;"
        "padding:8px 16px;border-radius:6px;text-decoration:none;'>"
        "Subscribe to Pro Weekly</a></p>",
        title="DemandRadar · Top 3",
        locale=locale,
    )
    return subject, text, html


__all__ = [
    "PLAN_DISPLAY",
    "cold_start_top3",
    "login_welcome",
    "paid_confirmation",
    "payment_failed",
    "referral_bonus",
    "waitlist_welcome",
]
