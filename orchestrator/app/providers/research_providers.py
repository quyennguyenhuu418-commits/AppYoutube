"""
Research providers — search and content fetch.

These providers are used by the Research Engine to discover and read sources.
They are independent of the LLM/TTS providers.

Selection: DuckDuckGo (free, no API key needed) is the default concrete
provider. When OpenAI is available a paid provider (SerpAPI / Tavily) can
be substituted by updating the factory functions below.
"""
from __future__ import annotations

import hashlib
import logging
from abc import ABC
from typing import Any

import httpx

from app.core.logging import get_logger
from app.providers.base import ContentFetchProvider, FetchResult, SearchProvider, SearchResult

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Source quality tiers — map domain patterns to tiers
# ---------------------------------------------------------------------------
_TIER1_DOMAINS = frozenset({
    "nature.com", "science.org", "pnas.org", "cell.com", "jstor.org",
    "sciencemag.org", "pmc.ncbi.nlm.nih.gov", "arxiv.org", "nature.com/articles",
    "academic.oup.com", "wiley.com", "springer.com", "elsevier.com",
})
_TIER2_DOMAINS = frozenset({
    "smithsonianmag.com", "smithsonian.org", "amnh.org", "bbc.com",
    "nationalgeographic.com", "mit.edu", "stanford.edu", "harvard.edu",
    "berkeley.edu", "ox.ac.uk", "cam.ac.uk", "edu", "sciencedaily.com",
})
_TIER3_DOMAINS = frozenset({
    "wikipedia.org", "britannica.com", "britannica.co.uk", "encyclopedia.com",
    "britannica", "livescience.com", "history.com", "archaeology.org",
})


def _domain_to_tier(domain: str) -> str:
    d = domain.lower()
    if any(d.endswith(t) for t in (".edu", ".gov", ".org") if "nature" in d or "science" in d or "pnas" in d):
        return "TIER1"
    for t1 in _TIER1_DOMAINS:
        if t1 in d:
            return "TIER1"
    for t2 in _TIER2_DOMAINS:
        if t2 in d:
            return "TIER2"
    for t3 in _TIER3_DOMAINS:
        if t3 in d:
            return "TIER3"
    return "TIER4"


# ---------------------------------------------------------------------------
# Search — DuckDuckGo via duckduckgo-search pip package
# ---------------------------------------------------------------------------

class DuckDuckGoSearchProvider(SearchProvider):
    """Free search using the duckduckgo-search library. No API key needed."""

    name = "duckduckgo"

    def search(self, query: str, tier_hint: str | None = None) -> list[SearchResult]:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            log.warning(
                "duckduckgo-search not installed. "
                "Install with: pip install duckduckgo-search"
            )
            return []

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=15))
        except Exception as exc:
            log.error("DuckDuckGo search failed for '%s': %s", query, exc)
            return []

        out: list[SearchResult] = []
        for r in results:
            url: str = r.get("href", "")
            title: str = r.get("title", "")
            snippet: str = r.get("body", "")
            if not url or not title:
                continue
            domain = _extract_domain(url)
            tier = tier_hint or _domain_to_tier(domain)
            out.append(SearchResult(
                url=url,
                title=title,
                snippet=snippet[:500],
                tier=tier,
                published_date=r.get("date", ""),
            ))
        return out


def _extract_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Content Fetch — httpx + readability extraction
# ---------------------------------------------------------------------------

class RequestsContentFetchProvider(ContentFetchProvider):
    """Fetch article content using httpx and extract readable text."""

    name = "httpx_fetch"

    TIMEOUT_SEC = 15.0

    def fetch(self, url: str) -> FetchResult | None:
        try:
            domain = _extract_domain(url)
            response = httpx.get(
                url,
                timeout=self.TIMEOUT_SEC,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; videoAI-research/1.0; "
                        "+https://github.com/videoai)"
                    ),
                },
            )
            response.raise_for_status()
            text = response.text

            # Try to extract readable content
            content = _extract_readable_content(url, text)

            return FetchResult(
                url=url,
                title=_extract_title(response.text, url),
                text_content=content,
                published_date="",
                author="",
                domain=domain,
            )
        except httpx.HTTPStatusError as exc:
            log.warning("HTTP %s fetching %s", exc.response.status_code, url)
            return None
        except Exception as exc:
            log.error("Failed to fetch %s: %s", url, exc)
            return None


def _extract_title(html: str, fallback_url: str) -> str:
    """Pull <title> from HTML."""
    import re
    m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return fallback_url


def _extract_readable_content(url: str, html: str) -> str:
    """
    Strip HTML tags and navigation to get plain text.
    For MVP we use a regex-based strip; in production use newspaper3k or
    Trafilatura. The engine will handle imperfect extraction gracefully.
    """
    import re

    # Remove <script>, <style>, <nav>, <footer>, <header>
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<nav[^>]*>.*?</nav>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<footer[^>]*>.*?</footer>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<header[^>]*>.*?</header>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Replace block elements with newlines
    html = re.sub(r"<(p|div|br|h[1-6]|li|tr)[^>]*>", "\n", html, flags=re.IGNORECASE)

    # Strip remaining tags
    text = re.sub(r"<[^>]+>", "", html)

    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:20000]  # Cap at 20k chars


# ---------------------------------------------------------------------------
# Provider factory (imported by research/engine.py)
# ---------------------------------------------------------------------------

def get_search_provider() -> SearchProvider:
    return DuckDuckGoSearchProvider()


def get_content_fetch_provider() -> ContentFetchProvider:
    return RequestsContentFetchProvider()
