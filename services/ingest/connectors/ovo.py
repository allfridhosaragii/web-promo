"""Konektor OVO — ovo.id/deals (Fase 1).

Sumber terverifikasi (SOURCES.md Rev 1 + verifikasi 2026-11-23):
- Listing https://ovo.id/deals memuat kartu promo via JS (Playwright Chromium).
- Halaman detail /deals/view/<id> adalah HTML statis.
- robots.txt ovo.id: Disallow */page/*, */?s=*, */?* (query string dilarang).
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


def extract_promo_links(html: str, base_url: str = "https://ovo.id/") -> list[str]:
    """Ekstrak URL detail promo kanonis `/deals/view/<id>` dari listing HTML ovo.id/deals."""
    tree = LexborHTMLParser(html)
    seen: set[str] = set()
    out: list[str] = []
    for a in tree.css("a[href]"):
        href = a.attributes.get("href", "")
        if "/deals/view/" not in href:
            continue
        full = canonical_url(urljoin(base_url, href))
        parsed = urlparse(full)
        if parsed.netloc not in ("ovo.id", "www.ovo.id"):
            continue
        path = parsed.path.rstrip("/")
        if not path.startswith("/deals/view/"):
            continue
        norm = f"https://ovo.id{path}"
        if norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def extract_detail_fields(html: str) -> tuple[str | None, str]:
    """Ekstrak (title, clean_body_text) dari HTML detail promo OVO."""
    tree = LexborHTMLParser(html)
    for node in tree.css("header, nav, footer, script, style, noscript"):
        node.decompose()
    h = tree.css_first("h3") or tree.css_first("h1") or tree.css_first("h2")
    title = h.text(strip=True) if h else None
    body = tree.css_first("main") or tree.css_first("body")
    raw_text = body.text(separator="\n", strip=True) if body else ""
    return title, clean_text(raw_text)


class OvoConnector(BaseConnector):
    source_id = "ovo"
    source_type = "public_web"
    base_url = "https://ovo.id/deals"
    robots_url = "https://ovo.id/robots.txt"

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
        if parsed.netloc not in ("ovo.id", "www.ovo.id"):
            return False
        if parsed.query or "/page/" in parsed.path:
            return False
        return super()._allowed_by_robots(url)

    async def _get_text(self, client: httpx.AsyncClient, url: str) -> str:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text

    async def _load_robots(self, client: httpx.AsyncClient) -> None:
        try:
            robots_txt = await self.fetch_with_retry(self._get_text, client, self.robots_url)
            self._robots = self._robots_parser(robots_txt, "https://ovo.id/")
        except Exception as exc:  # noqa: BLE001
            logger.warning("OVO gagal baca robots.txt: %s", exc)
            self._robots = None

    async def _render_listing(self) -> str:
        if self._html_fetcher is not None:
            return await self.fetch_with_retry(self._html_fetcher, self.base_url)

        from playwright.async_api import async_playwright

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    page = await browser.new_page(user_agent=self.user_agent)

                    async def _render(target_url: str) -> str:
                        await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(4000)
                        return await page.content()

                    return await self.fetch_with_retry(_render, self.base_url)
                finally:
                    await browser.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning("OVO gagal menjalankan Playwright Chromium: %s", exc)
            return ""

    async def fetch(self, limit: int = MAX_PROMOS_PER_RUN) -> list[RawItem]:
        headers = {"User-Agent": self.user_agent}
        items: list[RawItem] = []
        async with httpx.AsyncClient(
            headers=headers,
            timeout=self.timeout_seconds,
            follow_redirects=True,
            transport=self._transport,
        ) as client:
            await self._load_robots(client)
            if not self._allowed_by_robots(self.base_url):
                return []
            listing_html = await self._render_listing()
            if not listing_html:
                return []
            urls = [u for u in extract_promo_links(listing_html) if self._allowed_by_robots(u)][
                :limit
            ]
            for url in urls:
                try:
                    html = await self.fetch_with_retry(self._get_text, client, url)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("OVO gagal fetch %s: %s", url, exc)
                    continue
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
