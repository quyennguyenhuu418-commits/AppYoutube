"""
Mock research providers — return structural fixtures for testing and demo mode.

These providers ensure the engine can run end-to-end without any API keys.
Each fixture covers all schema sections but with minimal placeholder content.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.providers.base import ContentFetchProvider, FetchResult, SearchProvider, SearchResult

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Mock Search Results — structural template covering all tiers
# ---------------------------------------------------------------------------

MOCK_SEARCH_RESULTS: dict[str, list[SearchResult]] = {
    "ancient humans winter cold adaptation": [
        SearchResult(
            url="https://www.nature.com/articles/s41586-019-1290-4",
            title="The evolutionary history of cold adaptation in humans",
            snippet="We reconstructed the physiological adaptations that allowed ancient humans to survive in glacial environments...",
            tier="TIER1",
            published_date="2019-06-01",
        ),
        SearchResult(
            url="https://en.wikipedia.org/wiki/Neanderthal",
            title="Neanderthal - Wikipedia",
            snippet="Neanderthals inhabited Eurasia from the Pleistocene to approximately 40,000 years ago...",
            tier="TIER3",
            published_date="",
        ),
        SearchResult(
            url="https://www.smithsonianmag.com/science-nature/how-neanderthals-adapted-to-cold-180971856/",
            title="How Neanderthals Adapted to Cold - Smithsonian Magazine",
            snippet="New research reveals how Neanderthal anatomy and behavior helped them survive European winters...",
            tier="TIER2",
            published_date="2021-03-15",
        ),
        SearchResult(
            url="https://www.haaretz.com",
            title="Ice Age blog post on ancient survival",
            snippet="Ancient humans used fire and clothing...",
            tier="TIER4",
            published_date="",
        ),
    ],
    "fire control early humans": [
        SearchResult(
            url="https://en.wikipedia.org/wiki/Control_of_fire_by_early_humans",
            title="Control of fire by early humans",
            snippet="Evidence for the controlled use of fire dates back at least 400,000 years...",
            tier="TIER3",
            published_date="",
        ),
    ],
    "ice age megafauna mammoth hunting": [
        SearchResult(
            url="https://en.wikipedia.org/wiki/Megafauna",
            title="Megafauna - Wikipedia",
            snippet="During the Pleistocene epoch, megafauna such as mammoths roamed across Europe and Asia...",
            tier="TIER3",
            published_date="",
        ),
    ],
}

MOCK_FETCH_RESULTS: dict[str, FetchResult] = {
    "https://www.nature.com/articles/s41586-019-1290-4": FetchResult(
        url="https://www.nature.com/articles/s41586-019-1290-4",
        title="The evolutionary history of cold adaptation in humans",
        text_content=(
            "Ancient humans developed several cold-adapted physiological traits over the course of "
            "the Pleistocene. Neanderthals in particular showed robust skeletal features associated "
            "with cold adaptation, including a stocky body plan and short limbs. "
            "These adaptations complemented behavioral strategies such as fire use and shelter building. "
            "The earliest evidence for controlled fire dates to approximately 400,000 years ago at sites "
            "in Israel and Europe. Mammoth-bone huts found in Ukraine and Russia demonstrate sophisticated "
            "shelter construction. Isotopic evidence from Neanderthal remains suggests a diet high in "
            "animal fat, critical for surviving extreme cold where plant foods were unavailable."
        ),
        published_date="2019-06-01",
        author="Research Team",
        domain="nature.com",
    ),
}


class MockSearchProvider(SearchProvider):
    """Returns structural fixtures for queries. No API key needed."""

    name = "mock_search"

    def search(self, query: str, tier_hint: str | None = None) -> list[SearchResult]:
        log.info("[mock_search] query='%s' tier_hint='%s'", query, tier_hint)
        query_lower = query.lower()

        # Try exact match first
        for key, results in MOCK_SEARCH_RESULTS.items():
            if key in query_lower or query_lower in key:
                return list(results)

        # Fallback: return a generic fixture
        return [
            SearchResult(
                url=f"https://example.com/search?q={query[:20]}",
                title=f"Result for: {query[:60]}",
                snippet=f"Mock search result for the query about {query}. "
                        f"This is a structural fixture covering topic relevance.",
                tier=tier_hint or "TIER3",
                published_date="2024-01-01",
            ),
        ]


class MockContentFetchProvider(ContentFetchProvider):
    """Returns structured fixture content for known URLs."""

    name = "mock_fetch"

    def fetch(self, url: str) -> FetchResult | None:
        log.info("[mock_fetch] url='%s'", url)
        if url in MOCK_FETCH_RESULTS:
            return MOCK_FETCH_RESULTS[url]
        # Generate generic fixture content
        return FetchResult(
            url=url,
            title=f"Mock Article: {url[:60]}",
            text_content=(
                f"Mock content for: {url}. "
                "This is a structural fixture representing article text for research purposes. "
                "In a real run, this would contain the actual article content extracted from the web."
            ),
            published_date="2024-01-01",
            author="Mock Author",
            domain="example.com",
        )
