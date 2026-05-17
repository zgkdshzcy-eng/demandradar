"""Public newsletter endpoints.

Currently only /unsubscribe — the dispatcher itself runs as a scheduler job
or via CLI (see `app.cli`).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.core.unsubscribe import verify_token
from app.db.session import get_session
from app.models.user import User
from app.models.waitlist import WaitlistEntry

router = APIRouter(prefix="/api/newsletter", tags=["newsletter"])


_HTML = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>已退订 · DemandRadar</title>
<style>body{{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;background:#f6f7fb;padding:48px 24px;color:#111;}}
.box{{max-width:520px;margin:0 auto;background:#fff;border-radius:12px;padding:32px 36px;box-shadow:0 2px 8px rgba(0,0,0,.04);}}
h1{{margin-top:0}} a{{color:#3b82f6}}</style>
</head><body><div class="box">
<h1>{heading}</h1>
<p>{message}</p>
<p style="margin-top:24px;color:#888;font-size:13px;">
  你随时可以通过 <a href="{home}">DemandRadar</a> 重新订阅。
</p>
</div></body></html>"""


def _page(heading: str, message: str, *, status: int = 200) -> Response:
    from app.core.config import settings
    home = settings.public_base_url.rstrip("/") or "/"
    body = _HTML.format(heading=heading, message=message, home=home)
    return Response(content=body, media_type="text/html; charset=utf-8", status_code=status)


@router.get("/unsubscribe")
def unsubscribe(
    token: str | None = None,
    db: Session = Depends(get_session),
) -> Response:
    if not token:
        return _page("链接无效", "缺少退订 token。", status=400)
    parsed = verify_token(token)
    if parsed is None:
        return _page("链接无效", "退订 token 已损坏或已被篡改。", status=400)

    email, kind = parsed
    now = datetime.now(tz=timezone.utc)
    found = False
    if kind == "user":
        u = db.scalar(select(User).where(User.email == email))
        if u is not None:
            u.unsubscribed_at = u.unsubscribed_at or now
            found = True
    if kind == "wait" or not found:
        e = db.scalar(select(WaitlistEntry).where(WaitlistEntry.email == email))
        if e is not None:
            e.unsubscribed_at = e.unsubscribed_at or now
            found = True
    db.commit()

    logger.info("unsubscribe: email={} kind={} found={}", email, kind, found)
    if not found:
        return _page("已记录退订", f"我们没有在订阅列表里找到 {email}，但已避免后续向该地址发送。")
    return _page(
        "退订成功",
        f"<b>{email}</b> 已从邮件列表中移除。我们不会再向你发送 DemandRadar 周报。",
    )


__all__ = ["router"]
