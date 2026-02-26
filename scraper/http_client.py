from __future__ import annotations

import asyncio
import random
import time
from datetime import UTC, datetime

import httpx
from aiolimiter import AsyncLimiter
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config import settings
from logger import log
from proxy_pool import ProxyPool
from storage import SnapshotStorage, is_snapshot_fresh

# ---------------------------------------------------------------------------
# User-Agent rotation pool
# ---------------------------------------------------------------------------

_USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]


class _RetryableError(Exception):
    """Raised for HTTP errors that should trigger a proxy rotation + retry."""


class Fetcher:
    """Async HTTP client with proxy rotation, rate limiting, and MinIO snapshot caching."""

    def __init__(
        self,
        proxy_pool: ProxyPool,
        limiter: AsyncLimiter,
        semaphore: asyncio.Semaphore,
        storage: SnapshotStorage,
    ) -> None:
        self._proxy_pool = proxy_pool
        self._limiter = limiter
        self._semaphore = semaphore
        self._storage = storage

    async def fetch(self, url: str) -> HTMLParser:
        """Fetch *url* and return a parsed HTMLParser.

        Checks MinIO for a fresh snapshot first.  On cache miss, fetches live
        with a rotating proxy, uploads the snapshot, then returns the parser.
        """
        # --- Snapshot cache check ---
        key = SnapshotStorage.snapshot_key(url)
        snapshot_exists, last_modified = await self._storage.exists(key)

        if snapshot_exists and last_modified and is_snapshot_fresh(last_modified, settings.snapshot_ttl_days):
            log.debug("fetcher.cache_hit", url=url, key=key)
            html = await self._storage.get(key)
            if html:
                return HTMLParser(html)

        # --- Live fetch (with retry via tenacity) ---
        return await self._fetch_live(url, key)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=15),
        retry=retry_if_exception_type(_RetryableError),
        reraise=True,
    )
    async def _fetch_live(self, url: str, snapshot_key: str) -> HTMLParser:
        await self._proxy_pool.refresh_if_low()
        proxy = self._proxy_pool.get_proxy()

        async with self._semaphore:
            async with self._limiter:
                start = time.monotonic()
                try:
                    async with httpx.AsyncClient(
                        proxy=proxy,
                        timeout=20,
                        follow_redirects=True,
                        headers={"User-Agent": _random_ua()},
                    ) as client:
                        response = await client.get(url)

                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    log.info(
                        "fetcher.response",
                        url=url,
                        status_code=response.status_code,
                        elapsed_ms=elapsed_ms,
                    )

                    if response.status_code in (403, 429):
                        self._proxy_pool.mark_failed(proxy)
                        raise _RetryableError(
                            f"HTTP {response.status_code} from {url} — proxy rotated"
                        )

                    response.raise_for_status()

                except httpx.ProxyError as exc:
                    self._proxy_pool.mark_failed(proxy)
                    raise _RetryableError(f"Proxy error for {url}: {exc}") from exc

                except httpx.TimeoutException as exc:
                    raise _RetryableError(f"Timeout for {url}: {exc}") from exc

                except _RetryableError:
                    raise

                except httpx.HTTPStatusError as exc:
                    raise _RetryableError(f"HTTP error {exc.response.status_code} for {url}") from exc

        html_text = response.text

        # Upload snapshot asynchronously (fire-and-forget errors — not critical)
        try:
            await self._storage.put(snapshot_key, html_text)
        except Exception as exc:
            log.warning("fetcher.snapshot_upload_failed", url=url, error=str(exc))

        # Anti-ban jitter sleep
        await asyncio.sleep(random.uniform(0.3, 1.2))

        return HTMLParser(html_text)


def _random_ua() -> str:
    return random.choice(_USER_AGENTS)
