# TractorSpecs Scraper - Getting Started

This guide provides instructions for setting up and running the tractor specifications scraper.

## Prerequisites

- **Python 3.13+** (if running locally)
- **Docker & Docker Compose** (recommended)
- **PostgreSQL 15+**
- **MinIO** or S3-compatible storage
- **Webshare API Key** (optional, for proxy rotation)

## Method 1: Docker Compose (Easiest)

The included `docker-compose.yml` sets up PostgreSQL, MinIO, and the Scraper automatically.

1. **Configure Environment**:
   Ensure `scraper/.env` exists with correct values. The `DATABASE_URL` should point to the `db` service:
   `DATABASE_URL=postgresql://scraper:password@db:5432/tractors`

2. **Start the Stack**:
   ```bash
   docker compose up --build -d
   ```

3. **Initialize Storage**:
   Open the MinIO console at [http://localhost:9001](http://localhost:9001) (User: `minio`, Pass: `secret123`) and create a bucket named `tractor-snapshots`.

4. **Monitor Progress**:
   ```bash
   docker compose logs -f scraper
   ```

---

## Method 2: Local Execution

1. **Install Dependencies**:
   ```bash
   cd scraper
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   Copy the example and edit:
   ```bash
   cp .env.example .env
   ```

3. **Run Scraper**:
   ```bash
   python main.py
   ```

---

## Command Line Arguments

The scraper supports several flags to control execution:

- `--type [manufacturer|model]`: Process only specific targets.
- `--limit [number]`: Limit the number of targets processed in this run.
- `--retry-failed`: Attempt to recrawl targets marked as 'failed'.
- `--skip-seed`: Skip the initial manufacturer listing crawl.

Example:
```bash
python main.py --type model --limit 100
```

## Running Tests

### Unit & Parser Tests (No DB required)
```bash
cd scraper
pytest tests/test_transformer.py tests/test_parsers.py -v
```

### Pipeline Tests (Requires Database)
Ensure `DATABASE_URL` is set in your environment:
```bash
cd scraper
pytest tests/test_pipeline.py -v
```

## Troubleshooting

- **Database Connection**: Ensure the database is ready before the scraper starts. The scraper runs migrations automatically on launch.
- **Authentication**: If you see `FATAL: password authentication failed`, ensure the password in `.env` matches the `POSTGRES_PASSWORD` in `docker-compose.yml`. If you changed them recently, run `docker compose down -v` to reset the volume.
- **Proxies**: If crawls fail with 403s, verify your Webshare API key or disable proxies in `.env` if not needed for the target site.
