"""Data source collectors. Each collector emits RawSignal records.

Day 3-4 implemented: hn, reddit, producthunt, v2ex, github_trending, google_trends
"""
from __future__ import annotations

from app.collectors.base import BaseCollector, CollectStats, RawSignalPayload
from app.collectors.hn import HNCollector
from app.collectors.indiehackers import IndieHackersCollector
from app.collectors.lobsters import LobstersCollector
from app.collectors.producthunt import ProductHuntCollector
from app.collectors.reddit import RedditCollector
from app.collectors.trending import GitHubTrendingCollector
from app.collectors.trends import GoogleTrendsCollector
from app.collectors.v2ex import V2EXCollector
from app.collectors.weibo import WeiboHotCollector

# Name -> class registry; used by scheduler & CLI.
REGISTRY: dict[str, type[BaseCollector]] = {
    "hn": HNCollector,
    "reddit": RedditCollector,
    "producthunt": ProductHuntCollector,
    "v2ex": V2EXCollector,
    "github_trending": GitHubTrendingCollector,
    "google_trends": GoogleTrendsCollector,
    # D16
    "lobsters": LobstersCollector,
    "indiehackers": IndieHackersCollector,
    "weibo": WeiboHotCollector,
}

__all__ = [
    "BaseCollector",
    "CollectStats",
    "GitHubTrendingCollector",
    "GoogleTrendsCollector",
    "HNCollector",
    "IndieHackersCollector",
    "LobstersCollector",
    "ProductHuntCollector",
    "REGISTRY",
    "RawSignalPayload",
    "RedditCollector",
    "V2EXCollector",
    "WeiboHotCollector",
]
