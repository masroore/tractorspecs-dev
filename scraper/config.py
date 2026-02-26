from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    webshare_api_key: str
    database_url: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    target_base_url: str
    max_concurrency: int
    rate_limit_rps: float
    snapshot_ttl_days: int
    log_level: str
    json_export_dir: str


def _load() -> Settings:
    required = [
        "WEBSHARE_API_KEY",
        "DATABASE_URL",
        "MINIO_ENDPOINT",
        "MINIO_ACCESS_KEY",
        "MINIO_SECRET_KEY",
    ]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise ValueError(f"Missing required environment variables: {missing}")

    return Settings(
        webshare_api_key=os.environ["WEBSHARE_API_KEY"],
        database_url=os.environ["DATABASE_URL"],
        minio_endpoint=os.environ["MINIO_ENDPOINT"],
        minio_access_key=os.environ["MINIO_ACCESS_KEY"],
        minio_secret_key=os.environ["MINIO_SECRET_KEY"],
        minio_bucket=os.getenv("MINIO_BUCKET", "scraper-archive"),
        target_base_url=os.getenv("TARGET_BASE_URL", "https://www.tractordata.com"),
        max_concurrency=int(os.getenv("MAX_CONCURRENCY", "10")),
        rate_limit_rps=float(os.getenv("RATE_LIMIT_RPS", "5")),
        snapshot_ttl_days=int(os.getenv("SNAPSHOT_TTL_DAYS", "30")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        json_export_dir=os.getenv("JSON_EXPORT_DIR", "/app/json-data"),
    )


settings = _load()
