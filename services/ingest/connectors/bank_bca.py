"""Konektor BCA — Vertical Slice (promo.bca.co.id).

Sumber terverifikasi (SOURCES.md Rev 1, 2026-11-22):
- Discovery utama: https://promo.bca.co.id/sitemap.xml (sitemapindex -> 1..4/sitemap.xml)
- robots.txt promo.bca.co.id: Allow: /, Disallow: /*/search — JANGAN fetch path /search.
- Detail promo adalah HTML statis (httpx + selectolax LexborHTMLParser).
"""

from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx
from selectolax.lexbor import LexborHTMLParser

from pipeline.normalize import clean_text

from .base import BaseConnector, HealthStatus, RawItem, canonical_url

logger = logging.getLogger(__name__)

_SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
MAX_PROMOS_PER_RUN = 20


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)


def extract_links(html: str) -> list[str]:
    """Ekstrak href dari fixture/listing HTML (stdlib saja, tanpa selectolax)."""
    parser = _LinkParser()
    parser.feed(html)
    return parser.links


def extract_promo_links(html: str, base_url: str = "https://promo.bca.co.id/") -> list[str]:
    """Ekstrak URL detail promo kanonis dari listing HTML, tanpa duplikat dan tanpa /search."""
    seen: set[str] = set()
    out: list[str] = []
    for href in extract_links(html):
        full = canonical_url(urljoin(base_url, href))
        parsed = urlparse(full)
        if parsed.netloc != "promo.bca.co.id":
            continue
        if "/search" in parsed.path:
            continue
        if not (parsed.path.startswith("/id/all/20") or parsed.path.startswith("/id/campaign/")):
            continue
        if full not in seen:
            seen.add(full)
            out.append(full)
    return out


def parse_sitemap_locs(xml_text: str) -> tuple[list[str], list[str]]:
    """Kembalikan (child_sitemaps, page_urls) dari XML sitemap/sitemapindex."""
    root = ET.fromstring(xml_text)
    child_sitemaps = [
        el.text.strip()
        for el in root.findall(".//sm:sitemap/sm:loc", _SITEMAP_NS)
        if el.text and el.text.strip()
    ]
    page_urls = [
        el.text.strip()
        for el in root.findall(".//sm:url/sm:loc", _SITEMAP_NS)
        if el.text and el.text.strip()
    ]
    return child_sitemaps, page_urls


def extract_detail_fields(html: str) -> tuple[str | None, str]:
    """Ekstrak (title, clean_body_text) dari HTML detail promo BCA."""
    tree = LexborHTMLParser(html)
    h1 = tree.css_first("h1")
    title_el = tree.css_first("title")
    title = h1.text(strip=True) if h1 else (title_el.text(strip=True) if title_el else None)
    main = tree.css_first("main") or tree.css_first("body")
    raw_text = main.text(separator="\n", strip=True) if main else ""
    return title, clean_text(raw_text)


def _is_valid_promo_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc != "promo.bca.co.id":
        return False
    if "/search" in parsed.path:
        return False
    return parsed.path.startswith("/id/all/20") or parsed.path.startswith("/id/campaign/")


class BankBCAConnector(BaseConnector):
    source_id = "bca"
    source_type = "public_web"
    base_url = "https://promo.bca.co.id/"
    sitemap_url = "https://promo.bca.co.id/sitemap.xml"
    robots_url = "https://promo.bca.co.id/robots.txt"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        super().__init__()
        self._transport = transport

    def _allowed_by_robots(self, url: str) -> bool:
        # Python 3.12 RobotFileParser belum mendukung wildcard /*/search;
        # pastikan /search selalu diblokir sesuai robots.txt promo.bca.co.id.
        if "/search" in urlparse(url).path:
            return False
        return super()._allowed_by_robots(url)

    async def _get_text(self, client: httpx.AsyncClient, url: str) -> str:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text

    async def _load_robots(self, client: httpx.AsyncClient) -> None:
        try:
            robots_txt = await self.fetch_with_retry(self._get_text, client, self.robots_url)
            self._robots = self._robots_parser(robots_txt, self.base_url)
        except Exception as exc:  # noqa: BLE001 — tanpa robots, BaseConnector tetap sopan
            logger.warning("BCA gagal baca robots.txt: %s", exc)
            self._robots = None

    async def _discover_urls(self, client: httpx.AsyncClient, limit: int) -> list[str]:
        xml_text = await self.fetch_with_retry(self._get_text, client, self.sitemap_url)
        child_sitemaps, direct_urls = parse_sitemap_locs(xml_text)

        candidate_urls: list[str] = list(direct_urls)
        for child_url in child_sitemaps:
            if len(candidate_urls) >= limit:
                break
            if not self._allowed_by_robots(child_url):
                continue
            try:
                child_xml = await self.fetch_with_retry(self._get_text, client, child_url)
                _, locs = parse_sitemap_locs(child_xml)
                candidate_urls.extend(locs)
            except Exception as exc:  # noqa: BLE001 — skip child sitemap yang gagal
                logger.warning("BCA gagal baca child sitemap %s: %s", child_url, exc)

        seen: set[str] = set()
        out: list[str] = []
        for raw_url in candidate_urls:
            canon = canonical_url(raw_url)
            if not _is_valid_promo_url(canon):
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
                except Exception as exc:  # noqa: BLE001 — satu halaman gagal jangan gagalkan run
                    logger.warning("BCA gagal fetch %s: %s", url, exc)
                    continue
                title, text = extract_detail_fields(html)
                if not text or "Halaman tidak ditemukan" in text:
                    logger.info("BCA skip halaman kosong/404: %s", url)
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
                child_sitemaps, direct_urls = parse_sitemap_locs(xml_text)
                items_found = len(direct_urls)
                if child_sitemaps:
                    child_xml = await self.fetch_with_retry(
                        self._get_text, client, child_sitemaps[0]
                    )
                    _, locs = parse_sitemap_locs(child_xml)
                    items_found += len(locs)
            latency_ms = int((time.monotonic() - t0) * 1000)
            return HealthStatus(
                source_id=self.source_id,
                ok=items_found > 0,
                latency_ms=latency_ms,
                last_success_at=datetime.now(UTC),
                items_found=items_found,
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = int((time.monotonic() - t0) * 1000)
            return HealthStatus(
                source_id=self.source_id,
                ok=False,
                latency_ms=latency_ms,
                last_error=str(exc)[:200],
            )
