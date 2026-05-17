# DemandRadar

> Automated demand mining for indie hackers — scan public communities, surface high-willingness-to-pay SaaS pain points, and generate build-ready project briefs every week.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org/)

**Live**: [app.0-to-100.xyz](https://app.0-to-100.xyz) · **Status**: [app.0-to-100.xyz/status](https://app.0-to-100.xyz/status)

---

## What it does

DemandRadar is a full-stack SaaS that helps solo founders and indie hackers discover monetizable startup ideas from **real market signals** — not gut feelings.

1. **Collect** — scrapes public communities (Hacker News, V2EX, GitHub Trending, Google Trends, App Store reviews)
2. **Analyze** — LLM-powered pain point extraction + embedding-based clustering
3. **Score** — 10-dimension scoring model (pain intensity, frequency, willingness-to-pay, competition, differentiation, etc.)
4. **Generate** — build-ready project briefs with evidence citations
5. **Deliver** — weekly "Demand Radar Top 20" newsletter

## Architecture

```
public data → collectors → cleaning → LLM analysis → scoring → briefs/newsletter
                                    ↓
                              embedding + clustering (pgvector)
```

| Layer | Tech |
|-------|------|
| Backend | Python 3.11 + FastAPI + SQLAlchemy + APScheduler |
| Database | PostgreSQL 16 + pgvector |
| Cache/Queue | Redis |
| Frontend | Next.js 14 (App Router) + Tailwind + shadcn/ui |
| LLM | DeepSeek (primary) + Claude (fallback) |
| Email | Resend API |
| Deploy | Docker Compose + Caddy |

## Project structure

```
dianzi/
├── backend/
│   ├── app/
│   │   ├── collectors/     # Data source scrapers
│   │   ├── pipeline/       # Cleaning, dedup, embedding
│   │   ├── analyzer/       # LLM pain extraction + clustering
│   │   ├── scorer/         # 10-dimension scoring
│   │   ├── report/         # Weekly report + project brief generator
│   │   ├── notify/         # Email, Twitter, Weibo, GitHub sync
│   │   ├── api/            # FastAPI routes
│   │   ├── models/         # SQLAlchemy ORM
│   │   └── core/           # Config, LLM client, scheduler
│   ├── tests/
│   └── pyproject.toml
├── frontend/               # Next.js 14
│   ├── app/                # Pages (marketing, dashboard, status)
│   ├── components/         # UI components
│   └── messages/           # i18n (en, zh)
├── docs/                   # Setup guides
└── .env.example            # Environment template
```

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- DeepSeek API key ([platform.deepseek.com](https://platform.deepseek.com))

### Backend

```bash
cd backend
cp .env.example .env          # Fill in your API keys
docker compose up -d          # Start Postgres + Redis
pip install -e .
uvicorn app.main:app --reload --port 8000
```

Health check: `http://localhost:8000/healthz`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Landing page: `http://localhost:3000`

### Production deploy

See `docs/` for DigitalOcean + Docker Compose production setup.

## Features

- 🌐 **i18n**: English + Chinese (UI, emails, briefs, social posts)
- 📊 **Public dashboard**: MRR, subscriber count, system health at `/status`
- 📧 **Waitlist + email**: Resend API for confirmation emails and newsletters
- 🔗 **GitHub Sync**: Auto-publish high-score briefs to a public repo
- 🐦 **Social auto-posting**: Twitter & Weibo integration (configurable)
- 🔍 **SEO**: `hreflang`, `sitemap.xml`, Open Graph, structured data
- 📈 **Analytics**: Google Analytics + Baidu Tongji

## Data sources

| Source | Method | Frequency |
|--------|--------|-----------|
| Hacker News | Algolia API | 1h |
| V2EX | API + RSS | 2h |
| GitHub Trending | RSS | 1d |
| Google Trends | pytrends | 1d |
| App Store Reviews | RSS | 1d |

## Compliance

- Public data only — no scraping behind logins
- UGC aggregated and summarized, never republished in full
- Every insight links back to `source_url`
- Takedown requests: `takedown@0-to-100.xyz`

## License

MIT — see [LICENSE](LICENSE). The code is open; the prompt templates and operational data remain private (see `.gitignore`).

---

**Built by [@zgkdshzcy-eng](https://github.com/zgkdshzcy-eng)** · Part of the [0-to-100](https://0-to-100.xyz) ecosystem
