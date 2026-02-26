# 🐍 Scraper Implementation Plan

**Stack:** Python 3.13 · httpx · selectolax · asyncpg · asyncio · tenacity · aiolimiter · Webshare API · MinIO · Docker

---

## Overview

A production-grade async Python scraper that crawls a TractorData-style source site, extracts structured tractor specs, normalizes units, and upserts data into PostgreSQL. It is idempotent, restartable, proxy-rotated, and archives raw HTML to MinIO for replay.

**Key decisions:**
- BIGINT PKs (not UUIDs) — aligns with addendum-1 schema
- `ON CONFLICT (slug) DO UPDATE RETURNING id` pattern throughout
- selectolax over BeautifulSoup — 10–20× faster, sufficient CSS selector support
- Webshare rotating datacenter proxies; upgrade to residential if blocked
- aiolimiter caps at 5 req/s globally; asyncio Semaphore caps concurrency at 10
- MinIO stores raw HTML snapshots; skip re-fetch if snapshot exists and age < 30 days
- `crawl_targets` table drives all crawl state — enables full restartability
- No Celery for MVP — asyncio + semaphore is sufficient; add Celery in future for distributed crawling

---

## Directory Structure

```
scraper/
├── Dockerfile
├── requirements.txt
├── .env.example
├── config.py
├── main.py
├── logger.py
├── db.py
├── storage.py
├── proxy_pool.py
├── http_client.py
├── transformer.py
├── pipeline.py
├── crawler/
│   ├── __init__.py
│   ├── manufacturers.py
│   ├── series.py
│   └── models.py
├── parsers/
│   ├── __init__.py
│   ├── manufacturer_parser.py
│   ├── series_parser.py
│   └── model_parser.py
├── migrations/
│   └── 001_crawl_targets.sql
└── tests/
    ├── conftest.py
    ├── fixtures/
    │   ├── manufacturer_listing.html
    │   ├── series_page.html
    │   └── model_page.html
    ├── test_transformer.py
    ├── test_parsers.py
    └── test_pipeline.py
```

---

## Step 1 — Project Scaffold & Dependencies

**File:** `scraper/requirements.txt`

```
httpx[asyncio]>=0.27
selectolax>=0.3
asyncpg>=0.30
tenacity>=8.3
aiolimiter>=1.1
aiobotocore>=2.13
python-dotenv>=1.0
structlog>=24.0
orjson>=3.10
rich>=13.0
pytest>=8.0
pytest-asyncio>=0.24
```

**File:** `scraper/.env.example`

```
WEBSHARE_API_KEY=
DATABASE_URL=postgresql://tractorspecs:secret@db:5432/tractorspecs
MINIO_ENDPOINT=http://minio:9000
MINIO_ACCESS_KEY=
MINIO_SECRET_KEY=
MINIO_BUCKET=scraper-archive
TARGET_BASE_URL=https://www.tractordata.com
MAX_CONCURRENCY=10
RATE_LIMIT_RPS=5
SNAPSHOT_TTL_DAYS=30
LOG_LEVEL=INFO
```

---

## Step 2 — Configuration Module

**File:** `scraper/config.py`

- Use `python-dotenv` to load `.env` at module import
- Expose a frozen `Settings` dataclass with all environment variables typed
- Validate all required fields at startup; raise `ValueError` with a descriptive message if any are missing
- Expose a module-level `settings` singleton imported everywhere else

```python
from dataclasses import dataclass
import os
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

def _load() -> Settings:
    required = ["WEBSHARE_API_KEY", "DATABASE_URL", "MINIO_ENDPOINT",
                "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise ValueError(f"Missing required env vars: {missing}")
    return Settings(
        webshare_api_key=os.environ["WEBSHARE_API_KEY"],
        database_url=os.environ["DATABASE_URL"],
        minio_endpoint=os.environ["MINIO_ENDPOINT"],
        minio_access_key=os.environ["MINIO_ACCESS_KEY"],
        minio_secret_key=os.environ["MINIO_SECRET_KEY"],
        minio_bucket=os.getenv("MINIO_BUCKET", "scraper-archive"),
        target_base_url=os.getenv("TARGET_BASE_URL", "https://www.tractordata.com"),
        max_concurrency=int(os.getenv("MAX_CONCURRENCY", 10)),
        rate_limit_rps=float(os.getenv("RATE_LIMIT_RPS", 5)),
        snapshot_ttl_days=int(os.getenv("SNAPSHOT_TTL_DAYS", 30)),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )

settings = _load()
```

---

## Step 3 — Structured Logger

**File:** `scraper/logger.py`

- Use `structlog` with JSON processor chain in production, colored console in dev
- Log level controlled by `settings.log_level`
- Every HTTP log entry includes: `url`, `status_code`, `elapsed_ms`, `proxy_host`
- Every DB log entry includes: `table`, `operation`, `rows_affected`
- Export a module-level `log` instance for consistent use across all modules

---

## Step 4 — Database Layer

**File:** `scraper/db.py`

- `async init_db(dsn: str) -> asyncpg.Pool` — create pool with min 2 / max 10 connections; run `CREATE EXTENSION IF NOT EXISTS pg_trgm`
- `async close_db(pool: asyncpg.Pool)` — graceful pool shutdown
- `async run_migrations(pool)` — reads and executes all `.sql` files from `migrations/`
- Helper `async execute_returning_id(conn, sql, *args) -> int` — executes INSERT ... RETURNING id, returns integer

**File:** `scraper/migrations/001_crawl_targets.sql`

```sql
CREATE TABLE IF NOT EXISTS crawl_targets (
    id          BIGSERIAL PRIMARY KEY,
    url         TEXT NOT NULL UNIQUE,
    type        VARCHAR(20) NOT NULL CHECK (type IN ('manufacturer', 'series', 'model')),
    parent_id   BIGINT,
    meta        JSONB DEFAULT '{}',
    last_crawled_at TIMESTAMPTZ,
    status      VARCHAR(20) DEFAULT 'pending'
                    CHECK (status IN ('pending', 'in_progress', 'done', 'failed')),
    content_hash    VARCHAR(64),
    error_message   TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crawl_targets_status_type
    ON crawl_targets (status, type);

CREATE INDEX IF NOT EXISTS idx_crawl_targets_parent
    ON crawl_targets (parent_id);
```

The `meta` JSONB column stores context like `manufacturer_id`, `series_id` so model crawlers know which FK to use without extra lookups.

---

## Step 5 — Proxy Pool

**File:** `scraper/proxy_pool.py`

```python
class ProxyPool:
    def __init__(self, api_key: str) -> None: ...

    async def load_proxies(self) -> None:
        # GET https://proxy.webshare.io/api/v2/proxy/list/?page_size=100
        # Authorization: Token {api_key}
        # Parse JSON results, store list of proxy dicts

    def get_proxy(self) -> str:
        # Return formatted http://{username}:{password}@{proxy_address}:{port}
        # Random choice from pool

    def mark_failed(self, proxy_str: str) -> None:
        # Remove proxy from pool for current session
        # Log warning with proxy host

    async def refresh_if_low(self, threshold: int = 5) -> None:
        # Re-call load_proxies() if len(self.proxies) < threshold
```

Behavior:
- On `load_proxies`, fetch page 1 (100 proxies). If `count > 100`, fetch subsequent pages.
- Store full dict per proxy for metadata; expose only formatted string via `get_proxy()`
- Thread-safe access not required (single async event loop)

---

## Step 6 — HTTP Client

**File:** `scraper/http_client.py`

```python
class Fetcher:
    def __init__(
        self,
        proxy_pool: ProxyPool,
        limiter: AsyncLimiter,
        semaphore: asyncio.Semaphore,
        storage: SnapshotStorage,
    ) -> None: ...

    async def fetch(self, url: str) -> HTMLParser:
        # 1. Compute snapshot key from URL
        # 2. If snapshot exists and age < SNAPSHOT_TTL_DAYS, parse from MinIO and return
        # 3. Acquire semaphore + rate limiter
        # 4. Pick proxy from pool
        # 5. GET with httpx.AsyncClient(proxies=proxy, timeout=20, follow_redirects=True)
        # 6. On 403/429: mark_failed(proxy), raise to trigger tenacity retry
        # 7. On success: upload raw HTML to MinIO, return HTMLParser(response.text)
```

Decorators applied to `fetch`:
- `@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=15), reraise=True)`

User-Agent rotation:
- `random_ua() -> str` — pool of 10 real Chrome/Safari desktop UAs

Random jitter sleep:
- After each successful fetch: `await asyncio.sleep(random.uniform(0.3, 1.2))`

---

## Step 7 — MinIO Snapshot Storage

**File:** `scraper/storage.py`

```python
class SnapshotStorage:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str) -> None:
        # Initialize aiobotocore session

    async def exists(self, key: str) -> tuple[bool, datetime | None]:
        # HEAD object; return (exists, last_modified)

    async def get(self, key: str) -> str | None:
        # Download object; decode UTF-8; return string

    async def put(self, key: str, html: str) -> None:
        # Upload html.encode('utf-8') with ContentType text/html

    @staticmethod
    def snapshot_key(url: str) -> str:
        # f"scraper-archive/{date.today().isoformat()}/{sha256(url.encode()).hexdigest()}.html"
```

Age check logic in `Fetcher.fetch()`:
- `(datetime.now(UTC) - last_modified).days < settings.snapshot_ttl_days`

---

## Step 8 — Parsers

All parser functions are pure (no I/O), accept `HTMLParser`, return typed dicts. Fixture HTML files in `tests/fixtures/` are used for unit tests.

### `scraper/parsers/manufacturer_parser.py`

```python
def parse_manufacturer_listing(html: HTMLParser) -> list[dict]:
    """
    Returns:
        [{"name": str, "slug": str, "url": str}, ...]

    Target: manufacturer listing page anchor tags.
    CSS selector must be tuned to the actual target site structure.
    Slugs derived from URL path or generated from name via build_slug().
    """
```

### `scraper/parsers/series_parser.py`

```python
def parse_manufacturer_page(html: HTMLParser) -> dict:
    """
    Returns:
    {
        "manufacturer": {"description": str | None, "country": str | None},
        "series": [
            {
                "name": str,
                "slug": str,
                "production_start": int | None,
                "production_end": int | None,
                "models": [{"name": str, "url": str}]
            }
        ]
    }
    """
```

### `scraper/parsers/model_parser.py`

```python
def parse_model_page(html: HTMLParser) -> dict:
    """
    Returns:
    {
        "name": str,
        "production_start_year": int | None,
        "production_end_year": int | None,
        "description": str | None,
        "horsepower_hp": float | None,
        "specs": [
            {"group": str, "key": str, "value": str, "unit": str | None}
        ]
    }

    Logic:
    - H1 = model name
    - Production years from subtitle/header paragraph
    - Spec tables: find all <table> with spec-like structure
      - <caption> or preceding <h3> = group name
      - Each <tr> with 2+ <td> = key/value row
    - HP extracted from Engine spec group, normalized to float
    """
```

---

## Step 9 — Transformer / Normalizer

**File:** `scraper/transformer.py`

### `normalize_spec(key: str, value: str) -> tuple[str, str | None]`

Handles:
- Strip whitespace, `\u00a0`, HTML entities
- Extract numeric part and unit from combined strings:
  - `"75.5 hp"` → `("75.5", "hp")`
  - `"1,498 cc"` → `("1498", "cc")`
  - `"112.7 mm (4.4\")"` → `("112.7", "mm")`
- Convert power units to hp float: `kW × 1.341`, `PS × 0.9863`, `CV × 0.9863`
- Normalize unit aliases: `"horsepower"` → `"hp"`, `"cubic centimeters"` → `"cc"`, `"inches"` → `"in"`

### `compute_spec_hash(specs: list[dict]) -> str`

```python
import hashlib, json

def compute_spec_hash(specs: list[dict]) -> str:
    canonical = json.dumps(
        sorted(specs, key=lambda x: (x["group"], x["key"])),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
```

Used in pipeline to skip DB writes when page content is unchanged.

### `build_slug(name: str) -> str`

- Lowercase
- Replace `&` with `and`
- Replace all non-alphanumeric characters with `-`
- Collapse multiple `-` → single `-`
- Strip leading/trailing `-`

---

## Step 10 — Database Pipeline

**File:** `scraper/pipeline.py`

All functions accept an `asyncpg.Connection` from the pool. Use `async with pool.acquire() as conn:` at the crawler level.

### `upsert_manufacturer(conn, data: dict) -> int`

```sql
INSERT INTO manufacturers (slug, name, country, description, name_search, created_at, updated_at)
VALUES ($1, $2, $3, $4, to_tsvector('english', $2), NOW(), NOW())
ON CONFLICT (slug) DO UPDATE
SET name=$2, country=$3, description=COALESCE($4, manufacturers.description),
    name_search=to_tsvector('english', $2), updated_at=NOW()
RETURNING id;
```

### `upsert_series(conn, manufacturer_id: int, data: dict) -> int`

```sql
INSERT INTO series (manufacturer_id, slug, name, production_start_year, production_end_year, created_at, updated_at)
VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
ON CONFLICT (manufacturer_id, slug) DO UPDATE
SET name=$3, production_start_year=COALESCE($4, series.production_start_year),
    production_end_year=COALESCE($5, series.production_end_year), updated_at=NOW()
RETURNING id;
```

### `upsert_model(conn, manufacturer_id: int, series_id: int | None, data: dict) -> tuple[int, bool]`

Returns `(model_id, specs_need_update)`.

1. SELECT existing `content_hash` by slug
2. Compute new hash from `data["specs"]`
3. If hashes match → INSERT/UPDATE model row but skip spec replacement, return `(id, False)`
4. Otherwise INSERT/UPDATE and return `(id, True)`

```sql
INSERT INTO models (manufacturer_id, series_id, slug, name, production_start_year,
    production_end_year, horsepower_hp, description,
    name_search, is_active, created_at, updated_at)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, to_tsvector('english', $4), TRUE, NOW(), NOW())
ON CONFLICT (slug) DO UPDATE
SET manufacturer_id=$1, series_id=COALESCE($2, models.series_id),
    production_start_year=COALESCE($5, models.production_start_year),
    production_end_year=COALESCE($6, models.production_end_year),
    horsepower_hp=COALESCE($7, models.horsepower_hp),
    description=COALESCE($8, models.description),
    name_search=to_tsvector('english', $4),
    updated_at=NOW()
RETURNING id;
```

### `replace_model_specs(conn, model_id: int, specs: list[dict])`

1. `DELETE FROM model_specifications WHERE model_id = $1`
2. Bulk insert using `conn.copy_records_to_table('model_specifications', records=[...], columns=[...])`

`copy_records_to_table` is asyncpg's fastest bulk insert — avoids round-trip per row.

### `update_crawl_target_status(conn, url: str, status: str, content_hash: str | None = None, error: str | None = None)`

```sql
UPDATE crawl_targets
SET status=$2, content_hash=COALESCE($3, content_hash),
    error_message=$4, last_crawled_at=NOW(), updated_at=NOW()
WHERE url=$1;
```

---

## Step 11 — Crawlers

### `scraper/crawler/manufacturers.py`

`async crawl_manufacturers(fetcher, pool, base_url) -> None`

1. Fetch manufacturer listing page at `{base_url}/`
2. Parse with `manufacturer_parser.parse_manufacturer_listing()`
3. For each manufacturer:
   a. `upsert_manufacturer()` → get `manufacturer_id`
   b. Enqueue into `crawl_targets` (type=`'manufacturer'`, meta=`{"manufacturer_id": id}`)
4. Use `INSERT INTO crawl_targets ... ON CONFLICT (url) DO NOTHING` — idempotent

### `scraper/crawler/series.py`

`async crawl_manufacturer_page(fetcher, pool, target: dict) -> None`

`target` is a row from `crawl_targets` (type=`'manufacturer'`).

1. Fetch manufacturer URL
2. Parse with `series_parser.parse_manufacturer_page()`
3. Update manufacturer row (description, country) if newly scraped
4. For each series: `upsert_series()` → get `series_id`
5. For each model URL in series: enqueue into `crawl_targets` (type=`'model'`, meta=`{"manufacturer_id": ..., "series_id": ...}`)
6. Mark crawl_target `done`

### `scraper/crawler/models.py`

`async crawl_model_page(fetcher, pool, target: dict) -> None`

1. Fetch model URL
2. Parse with `model_parser.parse_model_page()`
3. Normalize specs via `transformer.normalize_spec()` on each spec
4. `upsert_model()` → `(model_id, specs_need_update)`
5. If `specs_need_update`: `replace_model_specs()`
6. Mark crawl_target `done` with `content_hash`
7. On any exception: mark `failed`, store `str(e)` as `error_message`

---

## Step 12 — Main Orchestrator

**File:** `scraper/main.py`

```
main(args)
  ├── Load config, init logger
  ├── init_db() → pool
  ├── run_migrations(pool)
  ├── ProxyPool.load_proxies()
  ├── SnapshotStorage init
  ├── AsyncLimiter(settings.rate_limit_rps, 1)
  ├── asyncio.Semaphore(settings.max_concurrency)
  ├── Fetcher(proxy_pool, limiter, semaphore, storage)
  │
  ├── if args.type in (None, 'manufacturer'):
  │     crawl_manufacturers()  — seeds crawl_targets table
  │
  ├── if args.type in (None, 'manufacturer'):
  │     process_pending_targets(type='manufacturer')
  │
  └── if args.type in (None, 'model'):
        process_pending_targets(type='model')
```

### `async process_pending_targets(pool, fetcher, target_type, batch_size=50)`

```
loop:
  1. SELECT id, url, meta FROM crawl_targets
        WHERE status='pending' AND type=$1
        ORDER BY id
        LIMIT $2
        FOR UPDATE SKIP LOCKED
  2. If empty → break
  3. Mark all as 'in_progress'
  4. asyncio.gather(*[crawl_fn(target) for target in batch])
     (each crawl_fn marks its own target done/failed)
  5. Continue loop
```

`FOR UPDATE SKIP LOCKED` prevents duplicate work if ever run in parallel.

### CLI args via `argparse`:

```
python main.py                      # full crawl
python main.py --type manufacturer  # only manufacturer pages
python main.py --type model         # only model pages
python main.py --type model --limit 500  # process 500 model targets
python main.py --retry-failed       # requeue all failed targets
```

---

## Step 13 — Dockerfile

**File:** `scraper/Dockerfile`

```dockerfile
FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

---

## Step 14 — Docker Compose Integration

Add to the project's `docker-compose.yml`:

```yaml
scraper:
  build: ./scraper
  env_file: ./scraper/.env
  depends_on:
    - pgsql
    - minio
  networks:
    - sail
  profiles:
    - scraper
```

Using `profiles: [scraper]` keeps it out of the default `sail up` — run explicitly:

```bash
docker compose --profile scraper run scraper python main.py
docker compose --profile scraper run scraper python main.py --type model --limit 1000
docker compose --profile scraper run scraper python main.py --retry-failed
```

---

## Step 15 — Tests

**File:** `scraper/tests/test_transformer.py`

Coverage:
- `normalize_spec("Engine", "75.5 hp")` → `("75.5", "hp")`
- `normalize_spec("Displacement", "1,498 cc")` → `("1498", "cc")`
- `normalize_spec("Bore", "112.7 mm (4.4\")")` → `("112.7", "mm")`
- kW → hp conversion
- PS → hp conversion
- `build_slug("John Deere 1025R")` → `"john-deere-1025r"`
- `compute_spec_hash()` stable across dict ordering

**File:** `scraper/tests/test_parsers.py`

Coverage (using fixture HTML files):
- `parse_manufacturer_listing()` returns correct name/slug/url list
- `parse_model_page()` returns all spec groups
- `parse_model_page()` extracts HP correctly
- `parse_model_page()` handles missing production years gracefully

**File:** `scraper/tests/test_pipeline.py`

Coverage (using test asyncpg connection to local test DB):
- `upsert_manufacturer()` returns ID on first insert
- `upsert_manufacturer()` is idempotent — same ID on second call
- `upsert_model()` returns `specs_need_update=False` when hash unchanged
- `replace_model_specs()` deletes old specs before insert

---

## Implementation Order

| # | Task | File(s) |
|---|------|---------|
| 1 | Scaffold, requirements, .env | `requirements.txt`, `.env.example` |
| 2 | Config module | `config.py` |
| 3 | Logger | `logger.py` |
| 4 | DB layer + migration | `db.py`, `migrations/001_crawl_targets.sql` |
| 5 | Proxy pool | `proxy_pool.py` |
| 6 | MinIO storage | `storage.py` |
| 7 | HTTP client | `http_client.py` |
| 8 | Transformer | `transformer.py` |
| 9 | Parsers (all 3) | `parsers/*.py` |
| 10 | Pipeline | `pipeline.py` |
| 11 | Crawlers (all 3) | `crawler/*.py` |
| 12 | Main orchestrator | `main.py` |
| 13 | Dockerfile | `Dockerfile` |
| 14 | Docker Compose integration | project `docker-compose.yml` |
| 15 | Tests | `tests/*.py` |
