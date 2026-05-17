"""Operational CLI.

Usage:
  python -m app.cli collect hn --limit 50
  python -m app.cli collect reddit --limit 100
  python -m app.cli collect producthunt --limit 30
  python -m app.cli collect all
  python -m app.cli stats
"""
from __future__ import annotations

import asyncio

import typer
from sqlalchemy import func, select

import app.collectors as collectors_mod
from app.collectors import REGISTRY
from app.db.session import SessionLocal
from app.models.raw_signal import RawSignal

app_cli = typer.Typer(help="DemandRadar operational CLI", no_args_is_help=True)
collect_app = typer.Typer(help="Run collectors")
app_cli.add_typer(collect_app, name="collect")


def _run(coro):  # type: ignore[no-untyped-def]
    try:
        asyncio.run(coro)
    except KeyboardInterrupt:
        raise typer.Exit(code=130)


@collect_app.command("hn")
def collect_hn(limit: int = 100) -> None:
    cls = REGISTRY["hn"]
    stats = asyncio.run(cls(limit=limit).run())
    typer.echo(stats.as_dict())


@collect_app.command("reddit")
def collect_reddit(limit: int = 100, listing: str = "new") -> None:
    cls = REGISTRY["reddit"]
    stats = asyncio.run(cls(limit=limit, listing=listing).run())
    typer.echo(stats.as_dict())


@collect_app.command("producthunt")
def collect_producthunt(limit: int = 50) -> None:
    cls = REGISTRY["producthunt"]
    stats = asyncio.run(cls(limit=limit).run())
    typer.echo(stats.as_dict())


@collect_app.command("v2ex")
def collect_v2ex(limit: int = 100) -> None:
    cls = REGISTRY["v2ex"]
    stats = asyncio.run(cls(limit=limit).run())
    typer.echo(stats.as_dict())


@collect_app.command("github_trending")
def collect_gh_trending(limit: int = 75) -> None:
    cls = REGISTRY["github_trending"]
    stats = asyncio.run(cls(limit=limit).run())
    typer.echo(stats.as_dict())


@collect_app.command("google_trends")
def collect_gtrends(limit: int = 60) -> None:
    cls = REGISTRY["google_trends"]
    stats = asyncio.run(cls(limit=limit).run())
    typer.echo(stats.as_dict())


@collect_app.command("all")
def collect_all(limit: int = 100) -> None:
    """Run every registered collector serially."""
    async def _all() -> None:
        for name, cls in REGISTRY.items():
            typer.echo(f"--- {name} ---")
            stats = await cls(limit=limit).run()
            typer.echo(stats.as_dict())

    _run(_all())


@app_cli.command("dedupe")
def dedupe(limit: int = 5000) -> None:
    """Mark cross-source duplicates among recent unprocessed signals."""
    from app.pipeline.dedupe import run_dedupe

    with SessionLocal() as db:
        stats = run_dedupe(db, limit=limit)
    typer.echo(stats.as_dict())


@app_cli.command("embed")
def embed(batch_size: int = 64, max_batches: int = 50) -> None:
    """Embed unprocessed RawSignals lacking embeddings."""
    from app.pipeline.embed import run_embed_batch

    async def _go() -> None:
        with SessionLocal() as db:
            stats = await run_embed_batch(db, batch_size=batch_size, max_batches=max_batches)
        typer.echo(stats.as_dict())

    _run(_go())


@app_cli.command("cluster")
def cluster_cmd(
    eps: float = 0.30,
    min_samples: int = 3,
    batch: int = 2000,
) -> None:
    """Run DBSCAN clustering over recent embedded signals."""
    from app.pipeline.cluster import run_cluster

    with SessionLocal() as db:
        stats = run_cluster(db, eps=eps, min_samples=min_samples, batch=batch)
    typer.echo(stats.as_dict())


@app_cli.command("extract")
def extract_cmd(max_clusters: int = 10) -> None:
    """LLM-extract pain points from clusters lacking them."""
    from app.analyzer.extract import run_extract

    async def _go() -> None:
        with SessionLocal() as db:
            stats = await run_extract(db, max_clusters=max_clusters)
        typer.echo(stats.as_dict())

    _run(_go())


@app_cli.command("score")
def score_cmd(limit: int = 30) -> None:
    """Score un-scored PainPoints with the 10-dim model."""
    from app.scorer import run_score

    async def _go() -> None:
        with SessionLocal() as db:
            stats = await run_score(db, limit=limit)
        typer.echo(stats.as_dict())

    _run(_go())


@app_cli.command("brief")
def brief_cmd(max_briefs: int = 5, min_score: float = 70.0) -> None:
    """Generate Project Briefs for top-scored PainPoints lacking one."""
    from app.report import run_briefs

    async def _go() -> None:
        with SessionLocal() as db:
            stats = await run_briefs(db, max_briefs=max_briefs, min_score=min_score)
        typer.echo(stats.as_dict())

    _run(_go())


@app_cli.command("weekly")
def weekly_cmd(items: int = 20, period_days: int = 7) -> None:
    """Generate the weekly digest for the past N days."""
    from app.report.weekly import generate_weekly

    with SessionLocal() as db:
        stats = generate_weekly(db, items_limit=items, period_days=period_days)
    typer.echo(stats.as_dict())


@app_cli.command("send-weekly")
def send_weekly_cmd(
    issue_no: int | None = None,
    dry_run: bool = typer.Option(False, "--dry-run"),
    max_send: int | None = typer.Option(None, help="cap recipients sent per run"),
) -> None:
    """D15: dispatch the weekly issue via the new newsletter pipeline.

    - Idempotent (per-recipient log; safe to re-run).
    - Honours `unsubscribed_at` on users + waitlist entries.
    - Each email gets a per-recipient unsubscribe link.
    """
    from sqlalchemy import desc
    from app.notify.newsletter import dispatch_weekly
    from app.models.weekly_report import WeeklyReport

    with SessionLocal() as db:
        if issue_no is not None:
            r = db.scalar(select(WeeklyReport).where(WeeklyReport.issue_no == issue_no))
        else:
            r = db.scalar(select(WeeklyReport).order_by(desc(WeeklyReport.issue_no)).limit(1))
        if r is None:
            typer.echo("no weekly issue available")
            raise typer.Exit(code=1)
        stats = dispatch_weekly(db, r, dry_run=dry_run, max_send=max_send)
    typer.echo(stats.as_dict())


@app_cli.command("post-pending")
def post_pending_cmd(limit: int = 10) -> None:
    """D15: drain queued tweets via X API v2 (no-op when TWITTER_ENABLED=false)."""
    from app.notify.twitter import post_pending

    with SessionLocal() as db:
        stats = post_pending(db, limit=limit)
    typer.echo(stats.__dict__)


@app_cli.command("ph-candidates")
def ph_candidates_cmd(limit: int = 10) -> None:
    """D15: print the most recent ProductHunt-ready candidates."""
    from app.notify.producthunt import list_candidates

    with SessionLocal() as db:
        rows = list_candidates(db, limit=limit)
    for r in rows:
        typer.echo(f"--- #{r.id} · {r.title or '(no title)'} ---")
        typer.echo(r.body)
        typer.echo("")


billing_app = typer.Typer(help="Billing utilities (D10)")
app_cli.add_typer(billing_app, name="billing")
auth_app = typer.Typer(help="Auth utilities (D10)")
app_cli.add_typer(auth_app, name="auth")


@billing_app.command("issue-code")
def billing_issue_code(
    plan: str = typer.Option("weekly_pro", help="weekly_pro | brief_oneoff | studio"),
    days: int = typer.Option(30, help="duration in days (ignored for brief_oneoff)"),
    brief_id: int | None = typer.Option(None, help="required for brief_oneoff"),
    note: str = typer.Option("", help="free-form note baked into the code"),
) -> None:
    """Generate a redeem code (HMAC-signed) that customers can paste into /account."""
    from app.core.security import issue_redeem_code

    code = issue_redeem_code(plan, days=days, brief_id=brief_id, note=note)
    typer.echo(code)


@billing_app.command("refund")
def billing_refund(subscription_id: int) -> None:
    """Cancel a recurring sub or refund a one-time payment by local id."""
    from app.core import payments
    from app.models.subscription import Subscription

    with SessionLocal() as db:
        sub = db.get(Subscription, subscription_id)
        if sub is None:
            typer.echo(f"subscription {subscription_id} not found")
            raise typer.Exit(1)
        if sub.provider != "stripe":
            typer.echo(f"sub provider={sub.provider}, not refundable here")
            raise typer.Exit(1)
        try:
            result = payments.refund_subscription(sub)
        except (payments.PaymentsDisabled, ValueError) as e:
            typer.echo(f"error: {e}")
            raise typer.Exit(1)
        sub.status = (
            "refunded"
            if result["refunded"]
            else ("canceled" if result["canceled"] else sub.status)
        )
        db.commit()
        typer.echo(result)


@billing_app.command("plans")
def billing_plans() -> None:
    """List configured plan -> price-id mappings."""
    from app.core import payments

    typer.echo(f"stripe enabled: {payments.is_enabled()}")
    for name, spec in payments.PLANS.items():
        try:
            pid = payments.plan_to_price_id(name)
        except ValueError as e:
            pid = f"<unset: {e}>"
        typer.echo(f"  {name:<14} mode={spec.mode:<13} price={pid}")


@auth_app.command("issue-link")
def auth_issue_link(email: str) -> None:
    """Print a magic-link token (paste it into /api/auth/verify?token=... in the browser)."""
    from app.core.security import issue_magic_link_token

    typer.echo(issue_magic_link_token(email))


@app_cli.command("retry-failed-emails")
def retry_failed_emails_cmd(limit: int = 200) -> None:
    """D19: redrive any `email_dispatches` rows still in status='failed'."""
    from app.notify.retry import retry_failed

    with SessionLocal() as db:
        stats = retry_failed(db, limit=limit)
    typer.echo(stats.as_dict())


@app_cli.command("expire-redeem")
def expire_redeem_cmd() -> None:
    """D19: mark expired redeem subscriptions as `expired`."""
    from app.billing.expire import expire_redeem_subs

    with SessionLocal() as db:
        stats = expire_redeem_subs(db)
    typer.echo(stats.as_dict())


@app_cli.command("admin-digest")
def admin_digest_cmd() -> None:
    """D19: compute today's admin digest. Sends email when ADMIN_EMAIL is set."""
    from app.notify.admin_digest import collect, send_daily_digest

    with SessionLocal() as db:
        ok = send_daily_digest(db)
        if not ok:
            typer.echo("(no email sent — printing payload)")
            stats = collect(db)
            for label, value in stats.cards:
                typer.echo(f"  {label:30s} {value}")
        else:
            typer.echo("digest sent")


@app_cli.command("cold-start")
def cold_start_cmd(dry_run: bool = typer.Option(False, "--dry-run")) -> None:
    """D19: send the Top-3 re-engagement email to eligible signups."""
    from app.notify.cold_start import run as run_cold_start

    with SessionLocal() as db:
        stats = run_cold_start(db, dry_run=dry_run)
    typer.echo(stats.as_dict())


@app_cli.command("alert-test")
def alert_test_cmd(message: str = "test alert from CLI") -> None:
    """D19: send a one-off message to ADMIN_WEBHOOK_URL to verify wiring."""
    from app.core.alert import notify_admin

    ok = notify_admin("DemandRadar · alert test", message, level="info", key=None)
    typer.echo(f"sent={ok}")


@app_cli.command("stats")
def stats() -> None:
    """Print raw_signals counts grouped by source + clusters + pain points."""
    from app.models.brief import Brief
    from app.models.cluster import Cluster
    from app.models.pain_point import PainPoint

    with SessionLocal() as db:
        total = db.scalar(select(func.count()).select_from(RawSignal)) or 0
        by_source = db.execute(
            select(RawSignal.source, func.count()).group_by(RawSignal.source)
        ).all()
        clustered = (
            db.scalar(
                select(func.count()).select_from(RawSignal).where(RawSignal.cluster_id.is_not(None))
            )
            or 0
        )
        cluster_n = db.scalar(select(func.count()).select_from(Cluster)) or 0
        pain_n = db.scalar(select(func.count()).select_from(PainPoint)) or 0
        brief_n = db.scalar(select(func.count()).select_from(Brief)) or 0

    typer.echo(f"total raw_signals: {total}  (clustered: {clustered})")
    for src, n in by_source:
        typer.echo(f"  {src:14s} {n}")
    typer.echo(f"clusters:    {cluster_n}")
    typer.echo(f"pain_points: {pain_n}")
    typer.echo(f"briefs:      {brief_n}")


def main() -> None:
    # Force registry import (no-op but keeps lints happy)
    _ = collectors_mod.REGISTRY
    app_cli()


if __name__ == "__main__":
    main()
