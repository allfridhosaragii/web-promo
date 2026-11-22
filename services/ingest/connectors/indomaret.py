"""Konektor Indomaret — www.indomaret.co.id/promosi/ (Fase 1).

Sumber terverifikasi (2026-11-23):
- `klikindomaret.com/xpress/promo` memblokir remote Module Federation (`ap-mc.klikindomaret.com`
  mengembalikan `net::ERR_BLOCKED_BY_ORB`).
- Halaman resmi Indomaret `https://www.indomaret.co.id/promosi/` berupa HTML statis dengan
  bagian promo terstruktur (`Super Hemat`, `Paling Murah`, `Hemat Minggu Ini`, `Tebus Heboh`, dll.).
- `www.indomaret.co.id/robots.txt` mengembalikan HTML homepage (bukan file robots.txt),
  sehingga konektor tetap membatasi domain ke `www.indomaret.co.id` dan path `/promosi/`.
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

from .base import BaseConnector, HealthStatus, RawItem

logger = logging.getLogger(__name__)

MAX_PROMOS_PER_RUN = 20

_SKIP_HEADINGS = {"Katalog Promosi Indomaret"}


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def extract_promo_sections(html: str) -> list[tuple[str, str]]:
    """Ekstrak daftar (judul_bagian, clean_body_text) dari HTML https://www.indomaret.co.id/promosi/."""
    tree = LexborHTMLParser(html)
    for node in tree.css("header, nav, footer, script, style, noscript"):
        node.decompose()

    h2_titles = [
        h.text(strip=True)
        for h in tree.css("h2")
        if h.text(strip=True) and h.text(strip=True) not in _SKIP_HEADINGS
    ]
    h2_set = set(h2_titles)

    body = tree.css_first("main") or tree.css_first("body")
    if not body:
        return []
    lines = [
        line.strip() for line in body.text(separator="\n", strip=True).splitlines() if line.strip()
    ]

    sections: list[tuple[str, str]] = []
    cur_title: str | None = None
    cur_lines: list[str] = []
    for line in lines:
        if line in h2_set and line != cur_title:
            if cur_title and cur_lines:
                sections.append((cur_title, clean_text(f"{cur_title}\n" + "\n".join(cur_lines))))
            cur_title = line
            cur_lines = []
        elif line in _SKIP_HEADINGS:
            continue
        elif cur_title is not None:
            cur_lines.append(line)

    if cur_title and cur_lines:
        sections.append((cur_title, clean_text(f"{cur_title}\n" + "\n".join(cur_lines))))
    return sections


def extract_detail_fields(html: str) -> tuple[str | None, str]:
    """Ekstrak (title, clean_body_text) dari potongan HTML satu bagian promo Indomaret."""
    tree = LexborHTMLParser(html)
    for node in tree.css("header, nav, footer, script, style, noscript"):
        node.decompose()
    h = tree.css_first("h2") or tree.css_first("h1")
    title = h.text(strip=True) if h else None
    body = tree.css_first("body") or tree.root
    raw_text = body.text(separator="\n", strip=True) if body else ""
    return title, clean_text(raw_text)


class IndomaretConnector(BaseConnector):
    source_id = "indomaret"
    source_type = "public_web"
    base_url = "https://www.indomaret.co.id/promosi/"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        super().__init__()
        self._transport = transport

    def _allowed_by_robots(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.netloc == "www.indomaret.co.id" and parsed.path.startswith("/promosi")

    async def _get_text(self, client: httpx.AsyncClient, url: str) -> str:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text

    async def fetch(self, limit: int = MAX_PROMOS_PER_RUN) -> list[RawItem]:
        if not self._allowed_by_robots(self.base_url):
            return []
        headers = {"User-Agent": self.user_agent}
        async with httpx.AsyncClient(
            headers=headers,
            timeout=self.timeout_seconds,
            follow_redirects=True,
            transport=self._transport,
        ) as client:
            html = await self.fetch_with_retry(self._get_text, client, self.base_url)

        items: list[RawItem] = []
        for title, text in extract_promo_sections(html)[:limit]:
            if not text:
                continue
            section_url = f"{self.base_url}?section={_slugify(title)}"
            items.append(
                self.make_raw_item(source_url=section_url, text=text, title=title, html=None)
            )
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
                sections = extract_promo_sections(html)
            latency_ms = int((time.monotonic() - t0) * 1000)
            return HealthStatus(
                source_id=self.source_id,
                ok=len(sections) > 0,
                latency_ms=latency_ms,
                last_success_at=datetime.now(UTC),
                items_found=len(sections),
            )
        except Exception as exc:  # noqa: BLE001
            return HealthStatus(
                source_id=self.source_id,
                ok=False,
                latency_ms=int((time.monotonic() - t0) * 1000),
                last_error=str(exc)[:200],
            )
