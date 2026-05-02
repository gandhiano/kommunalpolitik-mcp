"""Conservative HTTP client for public SessionNet pages."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests


class SessionNetClient:
    """Fetch public SessionNet pages with caching and rate limiting."""

    def __init__(
        self,
        base_url: str,
        cache_dir: Path,
        user_agent: str = "Kommunalpolitik-MCP Witzenhausen Scraper/0.1",
        delay_seconds: float = 2.0,
        use_cache: bool = True,
    ):
        self.base_url = base_url.rstrip("/") + "/"
        self.cache_dir = cache_dir
        self.delay_seconds = delay_seconds
        self.use_cache = use_cache
        self.last_request_at = 0.0
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
            }
        )

    def absolute_url(self, href: str) -> str:
        return urljoin(self.base_url, href)

    def get_text(self, path_or_url: str, force: bool = False) -> str:
        url = self.absolute_url(path_or_url)
        cache_path = self._cache_path(url, suffix=".html")
        if self.use_cache and not force and cache_path.exists():
            return cache_path.read_text(encoding="utf-8", errors="replace")

        response = self._get(url)
        response.encoding = response.encoding or "utf-8"
        text = response.text
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(text, encoding="utf-8")
        return text

    def download(self, path_or_url: str, target_path: Path, force: bool = False) -> tuple[str, int]:
        url = self.absolute_url(path_or_url)
        if target_path.exists() and not force:
            data = target_path.read_bytes()
            return hashlib.sha256(data).hexdigest(), len(data)

        response = self._get(url)
        data = response.content
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(data)
        return hashlib.sha256(data).hexdigest(), len(data)

    def _get(self, url: str) -> requests.Response:
        parsed_base = urlparse(self.base_url)
        parsed_url = urlparse(url)
        if parsed_base.netloc != parsed_url.netloc:
            raise ValueError(f"Refusing to fetch outside SessionNet host: {url}")

        elapsed = time.monotonic() - self.last_request_at
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)

        response = self.session.get(url, timeout=30)
        self.last_request_at = time.monotonic()
        response.raise_for_status()
        return response

    def _cache_path(self, url: str, suffix: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}{suffix}"
