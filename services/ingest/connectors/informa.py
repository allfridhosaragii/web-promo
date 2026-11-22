"""Konektor Informa — informa.co.id/home-promotion (Fase 1).

Sumber terverifikasi (2026-11-23):
- Listing & detail di https://informa.co.id/home-promotion dirender oleh Nuxt/SPA,
  sehingga memerlukan Playwright Chromium untuk merender DOM.
- robots.txt informa.co.id: Allow: /, Disallow: /up.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

import httpx
from selectolax.lexbor import LexborHTMLParser

from pipeline.normalize import clean_text

from .base import BaseConnector, HealthStatus, RawItem, canonical_url

logger = logging.getLogger(__name__)

MAX_PROMOS_PER_RUN = 20

_CUTOFF_MARKERS = (
    "Belanja Sekarang Dengan",
    "Promo\nLainnya",
    "Promo Lainnya",
)


def extract_promo_links(html: str, base_url: str = "https://informa.co.id/") -> list[str]:
    """Ekstrak URL detail promo kanonis dari listing HTML informa.co.id/home-promotion."""
    tree = LexborHTMLParser(html)
    seen: set[str] = set()
    out: list[str] = []
    for a in tree.css("a"):
        href = a.attributes.get("href", "")
        if "/home-promotion/" not in href:
            continue
        full = canonical_url(urljoin(base_url, href))
        parsed = urlparse(full)
        if parsed.netloc != "informa.co.id":
            continue
        path = parsed.path.rstrip("/")
        if not path.startswith("/home-promotion/") or path == "/home-promotion":
            continue
        if path.endswith("/undefined"):
            continue
        if full not in seen:
            seen.add(full)
            out.append(full)
    return out


def extract_detail_fields(html: str) -> tuple[str | None, str]:
    """Ekstrak (title, clean_body_text) dari HTML detail promo Informa."""
    tree = LexborHTMLParser(html)
    h1 = tree.css_first("h1")
    title_el = tree.css_first("title")
    title = h1.text(strip=True) if h1 else (title_el.text(strip=True) if title_el else None)
    for node in tree.css("header, nav, footer, script, style, noscript"):
        node.decompose()
    body = tree.css_first("body") or tree.css_first("article")
    raw_text = body.text(separator="\n", strip=True) if body else ""
    for marker in _CUTOFF_MARKERS:
        idx = raw_text.find(marker)
        if idx != -1:
            raw_text = raw_text[:idx]
            break
    return title, clean_text(raw_text)


class InformaConnector(BaseConnector):
    source_id = "informa"
    source_type = "public_web"
    base_url = "https://informa.co.id/home-promotion"
    robots_url = "https://informa.co.id/robots.txt"

    def __init__(
        self,
        transport: httpx.AsyncBaseTransport | None = None,
        html_fetcher: Callable[[str], Awaitable[str]] | None = None,
    ) -> None:
        super().__init__()
        self._transport = transport
        self._html_fetcher = html_fetcher

    def _allowed_by_robots(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.netloc != "informa.co.id":
            return False
        if parsed.path.startswith("/up") or parsed.path.rstrip("/").endswith("/undefined"):
            return False
        return super()._allowed_by_robots(url)

    async def _get_text(self, client: httpx.AsyncClient, url: str) -> str:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text

    async def _load_robots(self, client: httpx.AsyncClient) -> None:
        try:
            robots_txt = await self.fetch_with_retry(self._get_text, client, self.robots_url)
            self._robots = self._robots_parser(robots_txt, "https://informa.co.id/")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Informa gagal baca robots.txt: %s", exc)
            self._robots = None

    async def _fetch_all_pages(self, limit: int) -> list[tuple[str, str]]:
        """Ambil listing dan detail HTML via html_fetcher injeksi atau Playwright Chromium."""
        if self._html_fetcher is not None:
            listing_html = await self.fetch_with_retry(self._html_fetcher, self.base_url)
            urls = [u for u in extract_promo_links(listing_html) if self._allowed_by_robots(u)][
                :limit
            ]
            pages: list[tuple[str, str]] = []
            for url in urls:
                try:
                    html = await self.fetch_with_retry(self._html_fetcher, url)
                    pages.append((url, html))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Informa gagal fetch %s: %s", url, exc)
            return pages

        from playwright.async_api import async_playwright

        pages = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page(user_agent=self.user_agent)

                async def _render(target_url: str, wait_ms: int = 4000) -> str:
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(wait_ms)
                    return await page.content()

                listing_html = await self.fetch_with_retry(_render, self.base_url, 5000)
                urls = [u for u in extract_promo_links(listing_html) if self._allowed_by_robots(u)][
                    :limit
                ]
                for url in urls:
                    try:
                        html = await self.fetch_with_retry(_render, url, 4000)
                        pages.append((url, html))
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Informa gagal render %s: %s", url, exc)
            finally:
                await browser.close()
        return pages

    async def fetch(self, limit: int = MAX_PROMOS_PER_RUN) -> list[RawItem]:
        headers = {"User-Agent": self.user_agent}
        async with httpx.AsyncClient(
            headers=headers,
            timeout=self.timeout_seconds,
            follow_redirects=True,
            transport=self._transport,
        ) as client:
            await self._load_robots(client)

        if not self._allowed_by_robots(self.base_url):
            logger.warning("Informa listing diblokir oleh robots.txt")
            return []

        pages = await self._fetch_all_pages(limit)
        items: list[RawItem] = []
        for url, html in pages:
            title, text = extract_detail_fields(html)
            if not text:
                continue
            items.append(self.make_raw_item(source_url=url, text=text, title=title, html=html))
        return items

    def parse(self, item: RawItem) -> RawItem:
        text = clean_text(item.text)
        title = item.title
        if item.html and not text:
            extracted_title, extracted_text = extract_detail_fields(item.html)
            title = title or extracted_title
            text = extracted_text
        return self.make_raw_item(
            source_url=item.source_url, text=text, title=title, html=item.html
        )

    async def health_check(self) -> HealthStatus:
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout_seconds,
                follow_redirects=True,
                transport=self._transport,
            ) as client:
                resp = await client.get(self.base_url)
                resp.raise_for_status()
            latency_ms = int((time.monotonic() - t0) * 1000)
            return HealthStatus(
                source_id=self.source_id,
                ok=True,
                latency_ms=latency_ms,
                last_success_at=datetime.now(UTC),
            )
        except Exception as exc:  # noqa: BLE001
            return HealthStatus(
                source_id=self.source_id,
                ok=False,
                latency_ms=int((time.monotonic() - t0) * 1000),
                last_error=str(exc)[:200],
            )
