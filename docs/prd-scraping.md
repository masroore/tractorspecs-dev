
# 🐍 SCRAPING ARCHITECTURE (Production-Ready)

## Objectives

1. Crawl:

   * Manufacturers
   * Series
   * Models
2. Extract structured specs
3. Normalize units
4. Store in PostgreSQL
5. Avoid IP bans
6. Be restartable + idempotent

---

# 🔐 Why Webshare Proxy API

Webshare gives:

* Rotating IP pool
* Residential options
* API-based credential management
* Country targeting
* High request throughput

For a site like TractorData clone target:

* Rotating datacenter proxies are enough initially
* Switch to residential if blocking begins

---

# 🌐 Webshare Integration Strategy

Webshare provides:

* Proxy list endpoint
* Username/password auth
* Proxy gateway format

Example proxy format:

```
http://username:password@proxy.webshare.io:port
```

---

# 🏗 Scraper Architecture Overview

```
scraper/
 ├── config.py
 ├── proxy_pool.py
 ├── http_client.py
 ├── crawler.py
 ├── parser.py
 ├── transformer.py
 ├── pipeline.py
 ├── db.py
 ├── main.py
```

---

# 🔑 1. Webshare Proxy Manager

## proxy_pool.py

Responsibilities:

* Fetch proxy list from Webshare API
* Maintain rotating pool
* Return random proxy per request
* Health-check proxies
* Remove failing proxies temporarily

---

### Webshare API Usage

Fetch proxy list:

```http
GET https://proxy.webshare.io/api/v2/proxy/list/
Authorization: Token YOUR_API_KEY
```

Store:

* host
* port
* username
* password

---

### Proxy Pool Logic

```python
import random
import httpx

class ProxyPool:
    def __init__(self, api_key):
        self.api_key = api_key
        self.proxies = []
    
    async def load_proxies(self):
        headers = {"Authorization": f"Token {self.api_key}"}
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://proxy.webshare.io/api/v2/proxy/list/",
                headers=headers
            )
            data = r.json()
            self.proxies = data["results"]

    def get_proxy(self):
        proxy = random.choice(self.proxies)
        return f"http://{proxy['username']}:{proxy['password']}@{proxy['proxy_address']}:{proxy['port']}"
```

---

# 🌐 2. HTTP Client (Rotating Proxy per Request)

## http_client.py

```python
import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, stop_after_attempt, wait_exponential

class Fetcher:
    def __init__(self, proxy_pool):
        self.proxy_pool = proxy_pool

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def fetch(self, url):
        proxy = self.proxy_pool.get_proxy()

        async with httpx.AsyncClient(
            proxies=proxy,
            timeout=20,
            headers={
                "User-Agent": self.random_ua()
            }
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return HTMLParser(response.text)

    def random_ua(self):
        return random.choice([
            "Mozilla/5.0 ... Chrome/123",
            "Mozilla/5.0 ... Safari/537",
        ])
```

---

# ⚡ 3. Rate Limiting Strategy

Even with rotating proxies:

Do NOT spam.

Use:

```python
from aiolimiter import AsyncLimiter

limiter = AsyncLimiter(5, 1)  # 5 requests per second
```

Wrap fetch:

```python
async with limiter:
    html = await fetcher.fetch(url)
```

---

# 🧠 4. Crawl Strategy (Depth-Controlled)

## Step 1 – Crawl Manufacturers

Parse manufacturer listing page.

Store:

* name
* slug
* URL

Queue series pages.

---

## Step 2 – Crawl Series

Parse:

* series name
* models list
* production range

Queue model pages.

---

## Step 3 – Crawl Model Page

Extract:

* Name
* Production years
* Spec groups
* Spec key/value pairs
* Engine info

---

# 🧪 5. Parser Strategy (selectolax)

selectolax is extremely fast.

Example:

```python
def parse_model_page(html):
    specs = []

    tables = html.css("table.specs")

    for table in tables:
        group = table.css_first("caption").text()

        for row in table.css("tr"):
            cols = row.css("td")
            if len(cols) >= 2:
                key = cols[0].text(strip=True)
                value = cols[1].text(strip=True)
                specs.append((group, key, value))

    return specs
```

---

# 🧹 6. Data Normalization Layer

transformer.py

Responsibilities:

* Convert HP strings → numeric
* Normalize units (inches → mm)
* Strip whitespace
* Remove duplicate specs
* Hash spec set for change detection

Store:

```python
spec_hash = sha256(json.dumps(sorted_specs))
```

If hash unchanged → skip update.

---

# 🗄 7. Database Insert (asyncpg)

Use:

```sql
INSERT INTO models (...) 
ON CONFLICT (slug)
DO UPDATE
SET ...
RETURNING id;
```

Then bulk insert specs.

---

# 🛡 Anti-Ban Strategy

1. Rotate proxy every request
2. Rotate user agent
3. Random sleep jitter (0.3–1.2s)
4. Limit concurrency (max 10 tasks)
5. Retry exponential backoff
6. Detect 403 → cooldown proxy

---

# 📦 HTML Snapshot Archiving

Store raw HTML in MinIO:

```
scraper-archive/{date}/{model_slug}.html
```

Benefits:

* Debug parsing errors
* Avoid re-fetching
* Audit trail

---

# 🧠 Incremental Update Strategy

Add table:

```sql
crawl_targets
-----------------
id
url
type (manufacturer|series|model)
last_crawled_at
status
content_hash
```

Crawler:

* Only re-fetch if last_crawled_at > 30 days
* Or if forced refresh

---

# 🧰 Docker Service

Add service:

```yaml
scraper:
  build: ./scraper
  environment:
    - WEB_SHARE_API_KEY=xxx
    - DATABASE_URL=postgresql://...
  depends_on:
    - db
```

Run as:

```
docker compose run scraper python main.py
```

---

# ⚖️ Scraping Ethics & Risk Management

You must:

* Respect robots.txt (optional but recommended)
* Throttle aggressively
* Avoid parallel flood crawling
* Consider adding attribution footer
* Avoid copyrighted images if necessary

---

# 📊 Scraper Performance Targets

Safe Target:

* 2–5 requests/sec
* ~10k model pages per hour max
* ~200k pages/day (upper limit with residential proxies)

For MVP:

* 5k–20k pages total likely

---

# 🧩 Future Enhancements

* Distributed scraping via Celery + Redis
* Proxy health scoring
* Automatic proxy refresh via Webshare API
* Scrape multiple niche sources
* AI-assisted spec parsing cleanup

---

# 🔥 Production-Grade Scraper Characteristics

✔ Async
✔ Rotating proxies
✔ Resilient retries
✔ Idempotent DB inserts
✔ Change detection via hash
✔ Snapshot archive
✔ Incremental crawl
✔ Configurable concurrency

