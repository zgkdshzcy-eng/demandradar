"""Trend alert API: subscribe to keyword-based painpoint spike notifications."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import current_user_required
from app.core.logging import logger
from app.db.session import get_session
from app.models.trend_alert import TrendAlert
from app.models.user import User

router = APIRouter(prefix="/api/trend-alerts", tags=["trend-alerts"])


class TrendAlertIn(BaseModel):
    keyword: str = Field(min_length=2, max_length=120)
    min_score: int = Field(default=70, ge=0, le=100)


class TrendAlertOut(BaseModel):
    id: int
    keyword: str
    min_score: int
    active: bool


@router.get("", response_model=list[TrendAlertOut])
def list_alerts(
    db: Session = Depends(get_session),
    user: User = Depends(current_user_required),
) -> list[TrendAlertOut]:
    rows = list(
        db.execute(
            select(TrendAlert).where(TrendAlert.user_id == user.id)
        ).scalars()
    )
    return [
        TrendAlertOut(id=r.id, keyword=r.keyword, min_score=r.min_score, active=r.active)
        for r in rows
    ]


@router.post("", response_model=TrendAlertOut)
def create_alert(
    body: TrendAlertIn,
    db: Session = Depends(get_session),
    user: User = Depends(current_user_required),
) -> TrendAlertOut:
    existing = db.scalar(
        select(TrendAlert).where(
            TrendAlert.user_id == user.id,
            TrendAlert.keyword == body.keyword.lower().strip(),
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="alert for this keyword already exists")

    alert = TrendAlert(
        user_id=user.id,
        keyword=body.keyword.lower().strip(),
        min_score=body.min_score,
        active=True,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    logger.info("trend_alert created user={} keyword={}", user.id, alert.keyword)
    return TrendAlertOut(id=alert.id, keyword=alert.keyword, min_score=alert.min_score, active=alert.active)


@router.delete("/{alert_id}")
def delete_alert(
    alert_id: int,
    db: Session = Depends(get_session),
    user: User = Depends(current_user_required),
) -> dict[str, bool]:
    alert = db.get(TrendAlert, alert_id)
    if alert is None or alert.user_id != user.id:
        raise HTTPException(status_code=404, detail="not found")
    db.delete(alert)
    db.commit()
    return {"ok": True}


@router.post("/{alert_id}/toggle")
def toggle_alert(
    alert_id: int,
    db: Session = Depends(get_session),
    user: User = Depends(current_user_required),
) -> TrendAlertOut:
    alert = db.get(TrendAlert, alert_id)
    if alert is None or alert.user_id != user.id:
        raise HTTPException(status_code=404, detail="not found")
    alert.active = not alert.active
    db.commit()
    return TrendAlertOut(id=alert.id, keyword=alert.keyword, min_score=alert.min_score, active=alert.active)
