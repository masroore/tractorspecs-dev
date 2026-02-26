FROM python:3.13-slim

WORKDIR /app

# Build dependencies for asyncpg (needs gcc + libpq)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default: run a full crawl
CMD ["python", "main.py"]
