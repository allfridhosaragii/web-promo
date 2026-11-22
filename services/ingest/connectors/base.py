"""Interface konektor standar — ARCHITECTURE.md §5.1 (WAJIB).

Setiap konektor WAJIB mengimplementasikan BaseConnector. Rate limit & retry
ada di base, bukan di tiap konektor. Tidak ada konektor yang memanggil httpx
langsung tanpa lewat base class.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.robotparser import RobotFileParser


# kw_only=True: field wajib `text` tidak boleh tertukar posisi dengan field
# ber-default (bug klasik dataclass: non-default setelah default -> TypeError
# saat definisi). Semua konstruksi RawItem WAJIB pakai keyword.
@dataclass(frozen=True, kw_only=True)
class RawItem:
    source_id: str  # mis. "bca"
    source_url: str  # URL kanonis, tanpa query tracking (UTM, __cf_chl_*)
    text: str  # teks mentah / HTML yang sudah dibersihkan
    title: str | None = None
    html: str | None = None  # HTML mentah, bila perlu re-parse
    media_urls: list[str] = field(default_factory=list)
    fetched_at: datetime | None = None  # UTC
    content_hash: str | None = None  # sha256(text) untuk dedup mentah


@dataclass(frozen=True)
class HealthStatus:
    source_id: str
    ok: bool
    latency_ms: int | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    items_found: int = 0


# Query param tracking yang WAJIB dibuang dari URL kanonis (SOURCES.md Rev 1).
_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "__cf_chl_tk",
    "__cf_chl_rt_tk",
    "fbclid",
    "gclid",
}


def canonical_url(url: str) -> str:
    """Buang query tracking + fragment. OVO: semua query string dilarang di robots."""
    parsed = urlparse(url)
    query = urlencode(
        [
            (k, v)
            for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if k.lower() not in _TRACKING_PARAMS
        ]
    )
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/") or "/", "", query, ""))


def hash_content(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class BaseConnector(ABC):
    source_id: str = ""
    source_type: str = "public_web"  # official_api | public_web | affiliate_feed | community
    base_url: str = ""
    # Rate limit & retry bawaan — JANGAN override ke yang lebih agresif tanpa persetujuan.
    # Default: <=1 req/detik/domain. BNI www.bni.co.id = 1 req/5 detik, hanya 14:00-22:00 UTC
    # (pengaman saja — konektor BNI wajib pakai bniexperience, bukan domain utama).
    rate_limit_per_second: float = 1.0
    max_retries: int = 2  # total percobaan = 1 + 2 retry, backoff eksponensial
    retry_backoff_seconds: float = 2.0
    timeout_seconds: float = 30.0
    user_agent: str = (
        "BuruPromo/1.0 (+https://burupromo.example/about; contact: admin@burupromo.example)"
    )

    def __init__(self) -> None:
        self._last_request_at: float = 0.0
        self._robots: RobotFileParser | None = None

    # -- abstract: wajib diimplementasi tiap konektor --------------------------------
    @abstractmethod
    async def fetch(self) -> list[RawItem]:
        """Ambil daftar item mentah dari listing/sitemap.
        WAJIB: hormati robots.txt, pakai rate limiter bawaan, jangan fetch URL
        yang di-Disallow, jangan bypass captcha/login. Kembalikan list kosong
        (bukan exception) kalau listing kosong.
        """

    @abstractmethod
    def parse(self, item: RawItem) -> RawItem:
        """Parse satu RawItem: bersihkan teks, ekstrak link/kanonis, normalisasi URL.
        TIDAK boleh memanggil LLM di sini. Gagal parse satu item = skip + log,
        jangan gagalkan seluruh fetch().
        """

    @abstractmethod
    async def health_check(self) -> HealthStatus:
        """Cek ringan: 1 request ke listing/sitemap. Dipakai admin + scheduler
        untuk kill switch otomatis kalau gagal beruntun.
        """

    # -- disediakan base class --------------------------------------------------------
    async def _rate_limit(self) -> None:
        min_interval = 1.0 / self.rate_limit_per_second if self.rate_limit_per_second > 0 else 0
        wait = min_interval - (time.monotonic() - self._last_request_at)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_request_at = time.monotonic()

    def _robots_parser(self, robots_txt: str, base: str) -> RobotFileParser:
        parser = RobotFileParser()
        parser.parse(robots_txt.splitlines())
        parser.url = base
        return parser

    def _allowed_by_robots(self, url: str) -> bool:
        """Tanpa robots.txt yang berhasil dibaca, anggap diizinkan TAPI tetap sopan.
        Kalau parser ada dan URL di-Disallow -> False (dilarang fetch)."""
        if self._robots is None:
            return True
        return bool(self._robots.can_fetch(self.user_agent, url))

    async def fetch_with_retry(self, fn, *args, **kwargs):
        """Retry bawaan: 1 + max_retries percobaan, backoff eksponensial."""
        last_exc: Exception | None = None
        for attempt in range(1 + self.max_retries):
            try:
                await self._rate_limit()
                return await fn(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 — retry lalu raise terakhir
                last_exc = exc
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_backoff_seconds * (2**attempt))
        assert last_exc is not None
        raise last_exc

    def make_raw_item(
        self, *, source_url: str, text: str, title: str | None = None, html: str | None = None
    ) -> RawItem:
        url = canonical_url(source_url)
        return RawItem(
            source_id=self.source_id,
            source_url=url,
            text=text,
            title=title,
            html=html,
            fetched_at=datetime.now(UTC),
            content_hash=hash_content(text),
        )
