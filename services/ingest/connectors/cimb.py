"""Konektor CIMB Niaga — www.cimbniaga.co.id (Fase 1).

Sumber terverifikasi (SOURCES.md Rev 1 + verifikasi 2026-11-23):
- Discovery utama via https://www.cimbniaga.co.id/sitemap/promo.xml (HTML statis di detail).
- robots.txt cimbniaga.co.id: Disallow /cgi-bin/, /jcr:content/*, /_jcr_content/*,
  /apps-content/*, /screen/*, /id/error/*, /en/error/*, /clientlib-site/.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
from selectolax.lexbor import LexborHTMLParser

from pipeline.normalize import clean_text

from .base import BaseConnector, HealthStatus, RawItem, canonical_url

logger = logging.getLogger(__name__)

MAX_PROMOS_PER_RUN = 20

_DISALLOWED_PREFIXES = (
    "/cgi-bin/",
    "/jcr:content/",
    "/_jcr_content/",
    "/apps-content/",
    "/screen/",
    "/id/error/",
    "/en/error/",
    "/clientlib-site/",
)


def extract_promo_links_from_sitemap(xml_text: str) -> list[str]:
    """Ekstrak URL detail promo `/id/personal/promo/promo-detail.*` dari sitemap/promo.xml."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in re.findall(r"<loc>(.*?)</loc>", xml_text):
        full = canonical_url(raw.strip())
        parsed = urlparse(full)
        if parsed.netloc != "www.cimbniaga.co.id":
            continue
        if not parsed.path.startswith("/id/personal/promo/promo-detail."):
            continue
        if full not in seen:
            seen.add(full)
            out.append(full)
    return out


def extract_detail_fields(html: str) -> tuple[str | None, str]:
    """Ekstrak (title, clean_body_text) dari HTML detail promo CIMB Niaga."""
    tree = LexborHTMLParser(html)
    detail = tree.css_first("[class*='detail']")
    scope = detail or tree.css_first("main") or tree.css_first("body")
    if not scope:
        return None, ""
    h1 = scope.css_first("h1")
    title = h1.text(strip=True) if h1 else None
    if not title:
        for h in scope.css("h2, h3"):
            t = h.text(strip=True)
            if t:
                title = t
                break
    for node in scope.css("header, nav, footer, script, style, noscript"):
        node.decompose()
    raw_text = scope.text(separator="\n", strip=True)
    return title, clean_text(raw_text)


class CimbConnector(BaseConnector):
    source_id = "cimb"
    source_type = "public_web"
    base_url = "https://www.cimbniaga.co.id/id/personal/promo"
    sitemap_url = "https://www.cimbniaga.co.id/sitemap/promo.xml"
    robots_url = "https://www.cimbniaga.co.id/robots.txt"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        super().__init__()
        self._transport = transport

    def _allowed_by_robots(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.netloc != "www.cimbniaga.co.id":
            return False
        if parsed.path.startswith(_DISALLOWED_PREFIXES):
            return False
        return super()._allowed_by_robots(url)

    async def _get_text(self, client: httpx.AsyncClient, url: str) -> str:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text

    async def _load_robots(self, client: httpx.AsyncClient) -> None:
        try:
            robots_txt = await self.fetch_with_retry(self._get_text, client, self.robots_url)
            self._robots = self._robots_parser(robots_txt, "https://www.cimbniaga.co.id/")
        except Exception as exc:  # noqa: BLE001
            logger.warning("CIMB gagal baca robots.txt: %s", exc)
            self._robots = None

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
            if not self._allowed_by_robots(self.sitemap_url):
                return []
            sitemap_xml = await self.fetch_with_retry(self._get_text, client, self.sitemap_url)
            urls = [
                u
                for u in extract_promo_links_from_sitemap(sitemap_xml)
                if self._allowed_by_robots(u)
            ][:limit]
            for url in urls:
                try:
                    html = await self.fetch_with_retry(self._get_text, client, url)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("CIMB gagal fetch %s: %s", url, exc)
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
                xml_text = await self.fetch_with_retry(self._get_text, client, self.sitemap_url)
                urls = extract_promo_links_from_sitemap(xml_text)
            latency_ms = int((time.monotonic() - t0) * 1000)
            return HealthStatus(
                source_id=self.source_id,
                ok=len(urls) > 0,
                latency_ms=latency_ms,
                last_success_at=datetime.now(UTC),
                items_found=len(urls),
            )
        except Exception as exc:  # noqa: BLE001
            return HealthStatus(
                source_id=self.source_id,
                ok=False,
                latency_ms=int((time.monotonic() - t0) * 1000),
                last_error=str(exc)[:200],
            )
