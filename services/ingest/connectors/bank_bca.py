"""Konektor BCA — STUB Fase 0 (disabled, belum vertical slice).

Sumber terverifikasi (SOURCES.md Rev 1, 2026-11-22):
- Listing: https://promo.bca.co.id/ (JS-rendered — butuh Playwright di vertical slice)
- Discovery utama: https://promo.bca.co.id/sitemap.xml
- robots.txt promo.bca.co.id: Allow: /, Disallow: /*/search — JANGAN fetch path /search.
- Detail contoh: https://promo.bca.co.id/id/all/2026/10/26/04/starting-lane

`fetch()` sengaja menolak di Fase 0: konektor belum aktif (status disabled di DB).
Vertical slice BCA akan mengimplementasikan fetch via sitemap + Playwright
untuk listing, dengan fixture di connectors/tests/fixtures/bca/.
"""

from __future__ import annotations

from html.parser import HTMLParser

from .base import BaseConnector, HealthStatus, RawItem


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


class BankBCAConnector(BaseConnector):
    source_id = "bca"
    source_type = "public_web"
    base_url = "https://promo.bca.co.id/"
    sitemap_url = "https://promo.bca.co.id/sitemap.xml"

    async def fetch(self) -> list[RawItem]:
        raise NotImplementedError(
            "BankBCAConnector belum aktif (Fase 0 stub, status disabled). "
            "Implementasi di vertical slice BCA: fetch via sitemap.xml, "
            "listing JS-rendered via Playwright. Jangan fetch live di Fase 0."
        )

    def parse(self, item: RawItem) -> RawItem:
        # Parse fixture: bersihkan teks + kanonis URL. LLM TIDAK dipanggil di sini.
        text = (item.text or "").strip()
        return self.make_raw_item(
            source_url=item.source_url, text=text, title=item.title, html=item.html
        )

    async def health_check(self) -> HealthStatus:
        return HealthStatus(
            source_id=self.source_id,
            ok=False,
            last_error="Konektor disabled di Fase 0 (stub, belum vertical slice).",
        )
