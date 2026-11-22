"""Konektor GoPay — gopay.co.id/promo (Fase 1).

Sumber terverifikasi (SOURCES.md Rev 1, 2026-11-22):
- Discovery utama: https://gopay.co.id/sitemap-promo.xml (dan listing https://gopay.co.id/promo)
- robots.txt gopay.co.id: Allow: /, Disallow: /promo?page, /promo?category, /id/, /*?_rsc=*
  -> JANGAN crawl /promo?page atau query string pada listing.
- Detail promo adalah HTML statis (httpx + selectolax LexborHTMLParser).
"""

from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

import httpx
from selectolax.lexbor import LexborHTMLParser

from pipeline.normalize import clean_text

from .base import BaseConnector, HealthStatus, RawItem, canonical_url

logger = logging.getLogger(__name__)

_SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
MAX_PROMOS_PER_RUN = 20


def extract_promo_links(html: str, base_url: str = "https://gopay.co.id/") -> list[str]:
    """Ekstrak URL detail promo kanonis dari listing HTML GoPay (tanpa query string)."""
    tree = LexborHTMLParser(html)
    seen: set[str] = set()
    out: list[str] = []
    for a in tree.css("a"):
        href = a.attributes.get("href", "")
        if not href or "?" in href:
            continue
        full = canonical_url(urljoin(base_url, href))
        parsed = urlparse(full)
        if parsed.netloc != "gopay.co.id":
            continue
        if not parsed.path.startswith("/promo/") or parsed.path == "/promo":
            continue
        if full not in seen:
            seen.add(full)
            out.append(full)
    return out


def parse_sitemap_urls(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    return [
        el.text.strip()
        for el in root.findall(".//sm:url/sm:loc", _SITEMAP_NS)
        if el.text and el.text.strip()
    ]


def extract_detail_fields(html: str) -> tuple[str | None, str]:
    """Ekstrak (title, clean_body_text) dari HTML detail promo GoPay, buang header/nav/footer."""
    tree = LexborHTMLParser(html)
    h1 = tree.css_first("h1")
    title_el = tree.css_first("title")
    title = h1.text(strip=True) if h1 else (title_el.text(strip=True) if title_el else None)
    for node in tree.css("header, nav, footer, script, style"):
        node.decompose()
    main = tree.css_first("main") or tree.css_first("article") or tree.css_first("body")
    raw_text = main.text(separator="\n", strip=True) if main else ""
    return title, clean_text(raw_text)


class GoPayConnector(BaseConnector):
    source_id = "gopay"
    source_type = "public_web"
    base_url = "https://gopay.co.id/promo"
    sitemap_url = "https://gopay.co.id/sitemap-promo.xml"
    robots_url = "https://gopay.co.id/robots.txt"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        super().__init__()
        self._transport = transport

    def _allowed_by_robots(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.path.startswith("/id/") or "_rsc=" in parsed.query:
            return False
        if parsed.path == "/promo" and (
            "page=" in parsed.query or "category=" in parsed.query or bool(parsed.query)
        ):
            return False
        return super()._allowed_by_robots(url)

    async def _get_text(self, client: httpx.AsyncClient, url: str) -> str:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text

    async def _load_robots(self, client: httpx.AsyncClient) -> None:
        try:
            robots_txt = await self.fetch_with_retry(self._get_text, client, self.robots_url)
            self._robots = self._robots_parser(robots_txt, "https://gopay.co.id/")
        except Exception as exc:  # noqa: BLE001
            logger.warning("GoPay gagal baca robots.txt: %s", exc)
            self._robots = None

    async def _discover_urls(self, client: httpx.AsyncClient, limit: int) -> list[str]:
        urls: list[str] = []
        try:
            xml_text = await self.fetch_with_retry(self._get_text, client, self.sitemap_url)
            urls = parse_sitemap_urls(xml_text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("GoPay gagal baca sitemap-promo.xml (%s), fallback ke listing", exc)

        if not urls and self._allowed_by_robots(self.base_url):
            html = await self.fetch_with_retry(self._get_text, client, self.base_url)
            urls = extract_promo_links(html)

        seen: set[str] = set()
        out: list[str] = []
        for raw_url in urls:
            canon = canonical_url(raw_url)
            parsed = urlparse(canon)
            if parsed.netloc != "gopay.co.id" or not parsed.path.startswith("/promo/"):
                continue
            if not self._allowed_by_robots(canon):
                continue
            if canon not in seen:
                seen.add(canon)
                out.append(canon)
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
                    logger.warning("GoPay gagal fetch %s: %s", url, exc)
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
                xml_text = await self.fetch_with_retry(self._get_text, client, self.sitemap_url)
                urls = parse_sitemap_urls(xml_text)
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
