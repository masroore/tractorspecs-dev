from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import aiobotocore.session

from logger import log

if TYPE_CHECKING:
    pass


class SnapshotStorage:
    """Stores and retrieves raw HTML snapshots from MinIO (S3-compatible)."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
    ) -> None:
        self._endpoint = endpoint
        self._access_key = access_key
        self._secret_key = secret_key
        self._bucket = bucket
        self._session = aiobotocore.session.get_session()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def exists(self, key: str) -> tuple[bool, datetime | None]:
        """Return (exists, last_modified) for the given object key."""
        try:
            async with self._client() as s3:
                resp = await s3.head_object(Bucket=self._bucket, Key=key)
                last_modified: datetime = resp["LastModified"]
                return True, last_modified
        except Exception as exc:
            if _is_not_found(exc):
                return False, None
            raise

    async def get(self, key: str) -> str | None:
        """Download an HTML snapshot; return None if not found."""
        try:
            async with self._client() as s3:
                resp = await s3.get_object(Bucket=self._bucket, Key=key)
                async with resp["Body"] as stream:
                    body = await stream.read()
                return body.decode("utf-8")
        except Exception as exc:
            if _is_not_found(exc):
                return None
            raise

    async def put(self, key: str, html: str) -> None:
        """Upload an HTML snapshot."""
        body = html.encode("utf-8")
        async with self._client() as s3:
            await s3.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=body,
                ContentType="text/html; charset=utf-8",
            )
        log.debug("storage.put", key=key, size=len(body))

    @staticmethod
    def snapshot_key(url: str) -> str:
        """Derive a deterministic MinIO object key from a URL.

        Pattern: scraper-archive/{YYYY-MM-DD}/{sha256(url)}.html
        Using today's date so each day's crawl lands in its own prefix.
        """
        digest = hashlib.sha256(url.encode()).hexdigest()
        return f"scraper-archive/{date.today().isoformat()}/{digest}.html"

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _client(self):  # type: ignore[return]
        return self._session.create_client(
            "s3",
            endpoint_url=self._endpoint,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
        )


def is_snapshot_fresh(last_modified: datetime, ttl_days: int) -> bool:
    """Return True if the snapshot is younger than *ttl_days*."""
    age = (datetime.now(UTC) - last_modified).days
    return age < ttl_days


def _is_not_found(exc: Exception) -> bool:
    """Detect S3/MinIO 404 errors from aiobotocore."""
    from botocore.exceptions import ClientError

    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        return code in ("404", "NoSuchKey")
    return False
