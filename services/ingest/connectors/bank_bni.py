"""Konektor BNI — bniexperience.bni.co.id/promo (Fase 1).

Sumber terverifikasi (SOURCES.md Rev 1):
- Wajib pakai subdomain `bniexperience.bni.co.id` (BUKAN `www.bni.co.id` yang
  punya Crawl-delay: 10, Request-rate: 1/5, Visit-time: 14:00-22:00 UTC).
- robots.txt bniexperience.bni.co.id: Allow: /, Disallow: /sliders, /promo/preview/*
- Listing & detail adalah HTML statis (httpx + selectolax LexborHTMLParser).
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

import httpx
from selectolax.lexbor import LexborHTMLParser

from pipeline.normalize import clean_text

from .base import BaseConnector, HealthStatus, RawItem, canonical_url

logger = logging.getLogger(__name__)

MAX_PROMOS_PER_RUN = 20


def extract_promo_links(html: str, base_url: str = "https://bniexperience.bni.co.id/") -> list[str]:
    """Ekstrak URL detail promo kanonis dari listing HTML bniexperience."""
    tree = LexborHTMLParser(html)
    seen: set[str] = set()
    out: list[str] = []
    for a in tree.css("a"):
        href = a.attributes.get("href", "")
        if "/promo/detail/" not in href:
            continue
        full = canonical_url(urljoin(base_url, href))
        parsed = urlparse(full)
        if parsed.netloc != "bniexperience.bni.co.id":
            continue
        if parsed.path.startswith("/promo/preview"):
            continue
        if full not in seen:
            seen.add(full)
            out.append(full)
    return out


def extract_detail_fields(html: str) -> tuple[str | None, str]:
    """Ekstrak (title, clean_body_text) dari HTML detail promo BNI, buang header/nav/footer."""
    tree = LexborHTMLParser(html)
    h1 = tree.css_first("h1")
    title_el = tree.css_first("title")
    title = h1.text(strip=True) if h1 else (title_el.text(strip=True) if title_el else None)
    for node in tree.css("header, nav, footer, script, style"):
        node.decompose()
    main = tree.css_first("main") or tree.css_first("article") or tree.css_first("body")
    raw_text = main.text(separator="\n", strip=True) if main else ""
    return title, clean_text(raw_text)


class BankBNIConnector(BaseConnector):
    source_id = "bni"
    source_type = "public_web"
    base_url = "https://bniexperience.bni.co.id/promo"
    surabaya_url = "https://bniexperience.bni.co.id/promo/surabaya"
    robots_url = "https://bniexperience.bni.co.id/robots.txt"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        super().__init__()
        self._transport = transport

    def _allowed_by_robots(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.netloc == "www.bni.co.id":
            return False
        if parsed.path.startswith("/sliders") or parsed.path.startswith("/promo/preview"):
            return False
        return super()._allowed_by_robots(url)

    async def _get_text(self, client: httpx.AsyncClient, url: str) -> str:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text

    async def _load_robots(self, client: httpx.AsyncClient) -> None:
        try:
            robots_txt = await self.fetch_with_retry(self._get_text, client, self.robots_url)
            self._robots = self._robots_parser(robots_txt, "https://bniexperience.bni.co.id/")
        except Exception as exc:  # noqa: BLE001
            logger.warning("BNI gagal baca robots.txt: %s", exc)
            self._robots = None

    async def _discover_urls(self, client: httpx.AsyncClient, limit: int) -> list[str]:
        candidates: list[str] = []
        for listing_url in (self.base_url, self.surabaya_url):
            if not self._allowed_by_robots(listing_url):
                continue
            try:
                html = await self.fetch_with_retry(self._get_text, client, listing_url)
                candidates.extend(extract_promo_links(html))
            except Exception as exc:  # noqa: BLE001
                logger.warning("BNI gagal baca listing %s: %s", listing_url, exc)

        seen: set[str] = set()
        out: list[str] = []
        for u in candidates:
            if not self._allowed_by_robots(u):
                continue
            if u not in seen:
                seen.add(u)
                out.append(u)
            if len(out) >= limit:
                break
        return out

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
            urls = await self._discover_urls(client, limit=limit)
            if not urls:
                return []
            for url in urls:
                if not self._allowed_by_robots(url):
                    continue
                try:
                    html = await self.fetch_with_retry(self._get_text, client, url)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("BNI gagal fetch %s: %s", url, exc)
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
        headers = {"User-Agent": self.user_agent}
        try:
            async with httpx.AsyncClient(
                headers=headers,
                timeout=self.timeout_seconds,
                follow_redirects=True,
                transport=self._transport,
            ) as client:
                html = await self.fetch_with_retry(self._get_text, client, self.base_url)
                urls = extract_promo_links(html)
            latency_ms = int((time.monotonic() - t0) * 1000)
            return HealthStatus(
                source_id=self.source_id,
                ok=len(urls) > 0,
                latency_ms=latency_ms,
                last_success_at=datetime.now(UTC),
                items_found=len(urls),
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = int((time.monotonic() - t0) * 1000)
            return HealthStatus(
                source_id=self.source_id,
                ok=False,
                latency_ms=latency_ms,
                last_error=str(exc)[:200],
            )
