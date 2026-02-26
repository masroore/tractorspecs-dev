from __future__ import annotations

import random
from typing import Any

import httpx

from logger import log


class ProxyPool:
    """Manages a rotating pool of Webshare proxies."""

    _API_BASE = "https://proxy.webshare.io/api/v2"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._proxies: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def load_proxies(self) -> None:
        """Fetch all proxies from the Webshare API."""
        headers = {"Authorization": f"Token {self._api_key}"}
        collected: list[dict[str, Any]] = []
        page = 1

        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                resp = await client.get(
                    f"{self._API_BASE}/proxy/list/",
                    headers=headers,
                    params={"page_size": 100, "page": page, "mode": "direct"},
                )
                resp.raise_for_status()
                data = resp.json()
                collected.extend(data.get("results", []))

                if not data.get("next"):
                    break

                page += 1

        self._proxies = collected
        log.info("proxy_pool.loaded", count=len(self._proxies))

    def get_proxy(self) -> str:
        """Return a random proxy URL."""
        if not self._proxies:
            raise RuntimeError("Proxy pool is empty — call load_proxies() first")
        proxy = random.choice(self._proxies)
        return self._format(proxy)

    def mark_failed(self, proxy_str: str) -> None:
        """Remove a failing proxy from the pool for this session."""
        before = len(self._proxies)
        self._proxies = [p for p in self._proxies if self._format(p) != proxy_str]
        after = len(self._proxies)
        if before != after:
            log.warning("proxy_pool.removed", proxy=_redact_proxy(proxy_str), remaining=after)

    async def refresh_if_low(self, threshold: int = 5) -> None:
        """Re-fetch the proxy list if the pool drops below *threshold*."""
        if len(self._proxies) < threshold:
            log.warning("proxy_pool.low", count=len(self._proxies), threshold=threshold)
            await self.load_proxies()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _format(proxy: dict[str, Any]) -> str:
        return (
            f"http://{proxy['username']}:{proxy['password']}"
            f"@{proxy['proxy_address']}:{proxy['port']}"
        )


def _redact_proxy(proxy_str: str) -> str:
    """Return proxy URL with password replaced by ***."""
    try:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(proxy_str)
        if parsed.password:
            netloc = parsed.netloc.replace(parsed.password, "***")
            return urlunparse(parsed._replace(netloc=netloc))
    except Exception:
        pass
    return proxy_str
