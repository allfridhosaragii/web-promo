"""Konektor Bank Mandiri — www.mandirikartukredit.com/hot-offer (Fase 1).

Sumber terverifikasi (2026-11-23):
- `www.bankmandiri.co.id/promo` hanya berisi navigasi dan mengarahkan ke
  `https://www.mandirikartukredit.com/hot-offer` untuk daftar promo resmi Mandiri.
- `https://www.mandirikartukredit.com/hot-offer` dan halaman detail `/hot-offer/*`
  berupa HTML statis lengkap (28 promo di listing utama).
- `mandirikartukredit.com/robots.txt`: `User-agent: * Disallow:` (kosong).
  Konektor tetap memblokir `.pdf` dan domain luar.
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

MAX_PROMOS_PER_RUN = 28


def extract_promo_links(
    html: str, base_url: str = "https://www.mandirikartukredit.com/"
) -> list[str]:
    """Ekstrak URL detail promo kanonis `/hot-offer/<slug>` dari listing mandirikartukredit.com."""
    tree = LexborHTMLParser(html)
    seen: set[str] = set()
    out: list[str] = []
    for a in tree.css("a[href]"):
        href = a.attributes.get("href", "")
        if "/hot-offer/" not in href:
            continue
        full = canonical_url(urljoin(base_url, href))
        parsed = urlparse(full)
        if parsed.netloc != "www.mandirikartukredit.com":
            continue
        path = parsed.path.rstrip("/")
        if not path.startswith("/hot-offer/") or path == "/hot-offer":
            continue
        if path.lower().endswith(".pdf"):
            continue
        if full not in seen:
            seen.add(full)
            out.append(full)
    return out


def extract_detail_fields(html: str) -> tuple[str | None, str]:
    """Ekstrak (title, clean_body_text) dari HTML detail promo Mandiri."""
    tree = LexborHTMLParser(html)
    for node in tree.css("header, nav, footer, script, style, noscript"):
        node.decompose()
    h = tree.css_first("h1") or tree.css_first("h2")
    title = h.text(strip=True) if h else None
    main = tree.css_first("main") or tree.css_first("article") or tree.css_first("body")
    raw_text = main.text(separator="\n", strip=True) if main else ""
    return title, clean_text(raw_text)


class BankMandiriConnector(BaseConnector):
    source_id = "mandiri"
    source_type = "public_web"
    base_url = "https://www.mandirikartukredit.com/hot-offer"
    robots_url = "https://www.mandirikartukredit.com/robots.txt"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        super().__init__()
        self._transport = transport

    def _allowed_by_robots(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.netloc != "www.mandirikartukredit.com":
            return False
        if parsed.path.lower().endswith(".pdf"):
            return False
        return super()._allowed_by_robots(url)

    async def _get_text(self, client: httpx.AsyncClient, url: str) -> str:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text

    async def _load_robots(self, client: httpx.AsyncClient) -> None:
        try:
            robots_txt = await self.fetch_with_retry(self._get_text, client, self.robots_url)
            self._robots = self._robots_parser(robots_txt, "https://www.mandirikartukredit.com/")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Mandiri gagal baca robots.txt: %s", exc)
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
            if not self._allowed_by_robots(self.base_url):
                return []
            listing_html = await self.fetch_with_retry(self._get_text, client, self.base_url)
            urls = [u for u in extract_promo_links(listing_html) if self._allowed_by_robots(u)][
                :limit
            ]
            for url in urls:
                try:
                    html = await self.fetch_with_retry(self._get_text, client, url)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Mandiri gagal fetch %s: %s", url, exc)
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
            return HealthStatus(
                source_id=self.source_id,
                ok=False,
                latency_ms=int((time.monotonic() - t0) * 1000),
                last_error=str(exc)[:200],
            )
