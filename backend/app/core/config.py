"""Centralized configuration via pydantic-settings.

All settings are loaded from environment variables (with `.env` fallback).
Never hard-code secrets in source code.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: str = Field("dev", alias="APP_ENV")
    app_host: str = Field("0.0.0.0", alias="APP_HOST")
    app_port: int = Field(8000, alias="APP_PORT")
    app_secret_key: str = Field("", alias="APP_SECRET_KEY")

    # Database / Redis
    database_url: str = Field(
        "postgresql+psycopg://demandradar:demandradar@localhost:5432/demandradar",
        alias="DATABASE_URL",
    )
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")

    # LLM - DeepSeek (primary)
    deepseek_api_key: str = Field("", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field("https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field("deepseek-chat", alias="DEEPSEEK_MODEL")

    # LLM - Anthropic (verifier)
    anthropic_api_key: str = Field("", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field("claude-sonnet-4-5", alias="ANTHROPIC_MODEL")

    # LLM - OpenAI compatible (fallback)
    openai_api_key: str = Field("", alias="OPENAI_API_KEY")
    openai_base_url: str = Field("https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_model: str = Field("gpt-4o-mini", alias="OPENAI_MODEL")

    # LLM - Aliyun DashScope (D17, fourth provider). OpenAI-compatible HTTP API.
    dashscope_api_key: str = Field("", alias="DASHSCOPE_API_KEY")
    dashscope_base_url: str = Field(
        "https://dashscope.aliyuncs.com/compatible-mode/v1", alias="DASHSCOPE_BASE_URL"
    )
    dashscope_model: str = Field("qwen-plus", alias="DASHSCOPE_MODEL")

    # Embeddings (OpenAI-compatible: OpenAI / DashScope / etc.)
    # Default dim=1024 matches DB schema (raw_signal.EMBEDDING_DIM).
    embedding_api_key: str = Field("", alias="EMBEDDING_API_KEY")
    embedding_base_url: str = Field(
        "https://api.openai.com/v1", alias="EMBEDDING_BASE_URL"
    )
    embedding_model: str = Field("text-embedding-3-small", alias="EMBEDDING_MODEL")
    embedding_dim: int = Field(1024, alias="EMBEDDING_DIM")

    # Cost guardrail
    llm_daily_budget_cny: float = Field(50.0, alias="LLM_DAILY_BUDGET_CNY")

    # SMTP for outbound email (weekly digest, etc.)
    smtp_host: str = Field("", alias="SMTP_HOST")
    smtp_port: int = Field(587, alias="SMTP_PORT")
    smtp_user: str = Field("", alias="SMTP_USER")
    smtp_password: str = Field("", alias="SMTP_PASSWORD")
    smtp_from: str = Field("DemandRadar <noreply@example.com>", alias="SMTP_FROM")
    smtp_use_tls: bool = Field(True, alias="SMTP_USE_TLS")

    # Resend API (alternative to SMTP, uses HTTPS port 443)
    resend_api_key: str = Field("", alias="RESEND_API_KEY")

    # Billing (D10/D12)
    # When STRIPE_SECRET_KEY is empty we degrade to redeem-code-only mode.
    stripe_secret_key: str = Field("", alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str = Field("", alias="STRIPE_WEBHOOK_SECRET")
    # Stripe Price IDs (recurring or one-time) — set per environment.
    stripe_price_weekly_pro: str = Field("", alias="STRIPE_PRICE_WEEKLY_PRO")
    stripe_price_studio: str = Field("", alias="STRIPE_PRICE_STUDIO")
    stripe_price_brief_oneoff: str = Field("", alias="STRIPE_PRICE_BRIEF_ONEOFF")
    public_base_url: str = Field("http://localhost:3000", alias="PUBLIC_BASE_URL")

    # Observability (D11)
    sentry_dsn: str = Field("", alias="SENTRY_DSN")
    sentry_traces_sample_rate: float = Field(0.0, alias="SENTRY_TRACES_SAMPLE_RATE")
    log_format: str = Field("text", alias="LOG_FORMAT")  # 'text' | 'json'
    log_level: str = Field("", alias="LOG_LEVEL")        # override; empty = auto
    metrics_enabled: bool = Field(True, alias="METRICS_ENABLED")

    # D15: outbound social automation
    twitter_bearer_token: str = Field("", alias="TWITTER_BEARER_TOKEN")
    # OAuth2 user access token with tweet.write — needed for POST /2/tweets.
    twitter_access_token: str = Field("", alias="TWITTER_ACCESS_TOKEN")
    twitter_enabled: bool = Field(False, alias="TWITTER_ENABLED")
    # Weibo auto-poster (optional, China side)
    weibo_access_token: str = Field("", alias="WEIBO_ACCESS_TOKEN")
    weibo_enabled: bool = Field(False, alias="WEIBO_ENABLED")
    # GitHub public-brief sync (optional, increases SEO + GitHub trending)
    github_sync_enabled: bool = Field(False, alias="GITHUB_SYNC_ENABLED")
    github_sync_token: str = Field("", alias="GITHUB_SYNC_TOKEN")
    github_sync_repo: str = Field("", alias="GITHUB_SYNC_REPO")
    github_sync_branch: str = Field("main", alias="GITHUB_SYNC_BRANCH")
    github_sync_min_score: float = Field(80.0, alias="GITHUB_SYNC_MIN_SCORE")
    # Newsletter dispatch tuning.
    newsletter_dispatch_per_minute: int = Field(60, alias="NEWSLETTER_DISPATCH_PER_MINUTE")
    newsletter_max_per_run: int = Field(2000, alias="NEWSLETTER_MAX_PER_RUN")

    # D19: Operational alerting + ops automation
    # Generic webhook (Slack incoming-webhook URL or Discord webhook URL).
    # Empty disables alerts; messages are JSON `{"text": "..."}`.
    admin_webhook_url: str = Field("", alias="ADMIN_WEBHOOK_URL")
    # Optional inbox to receive the daily admin digest. Empty disables it.
    admin_email: str = Field("", alias="ADMIN_EMAIL")
    # When > 0, alert when today's LLM spend crosses this fraction of the cap.
    llm_budget_alert_pct: float = Field(0.8, alias="LLM_BUDGET_ALERT_PCT")
    # Auto-tweet a brief when its painpoint scores >= this threshold.
    auto_tweet_min_score: float = Field(80.0, alias="AUTO_TWEET_MIN_SCORE")
    # Cold-start re-engagement email window (hours since signup, no purchase).
    cold_start_window_hours: int = Field(48, alias="COLD_START_WINDOW_HOURS")

    # Data sources
    reddit_client_id: str = Field("", alias="REDDIT_CLIENT_ID")
    reddit_client_secret: str = Field("", alias="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field("demandradar/0.1", alias="REDDIT_USER_AGENT")
    product_hunt_token: str = Field("", alias="PRODUCT_HUNT_TOKEN")

    @property
    def is_dev(self) -> bool:
        return self.app_env.lower() == "dev"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
