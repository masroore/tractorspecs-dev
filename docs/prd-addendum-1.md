# 🔧 Primary Architectural Changes

## Primary Keys Strategy

All tables:

```sql
id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY
```

Why BIGINT instead of INT?

* Safe up to billions of rows
* Future-proof if you expand to:

  * Farm equipment
  * Combines
  * Attachments
  * Global machinery DB

Index size impact is still minimal.

---

# 🔐 ID Obfuscation Strategy (SQIDs)

Package:

```
red-explosion/laravel-sqids
```

We do NOT expose numeric IDs.

Instead:

```php
$model->sqid
```

Routes use:

```php
Route::get('/tractor/{sqid}/{slug}', ...)
```

Decoding:

```php
$id = Sqids::decode($sqid)[0];
```

This gives:

* Clean URLs
* No sequential ID exposure
* Prevents scraping enumeration
* SEO-friendly

Example:

```
/tractor/jD8K3L/john-deere-1025r
```

---

# 🧱 Revised Database Model (MVP Optimized)

---

## manufacturers

```sql
id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
slug VARCHAR(160) UNIQUE NOT NULL,
name VARCHAR(160) NOT NULL,
country VARCHAR(120),
founded_year SMALLINT,
description TEXT,
logo_path VARCHAR(255),

name_search TEXT,
created_at TIMESTAMP,
updated_at TIMESTAMP
```

Indexes:

```sql
INDEX idx_manufacturers_slug (slug),
GIN INDEX idx_manufacturers_search (name_search gin_trgm_ops)
```

---

## categories

```sql
id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
slug VARCHAR(160) UNIQUE NOT NULL,
name VARCHAR(160) NOT NULL,
description TEXT,
created_at TIMESTAMP,
updated_at TIMESTAMP
```

---

## series

```sql
id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
manufacturer_id BIGINT UNSIGNED NOT NULL,
slug VARCHAR(160) NOT NULL,
name VARCHAR(160) NOT NULL,
production_start_year SMALLINT,
production_end_year SMALLINT,
created_at TIMESTAMP,
updated_at TIMESTAMP
```

Indexes:

```sql
INDEX idx_series_manufacturer (manufacturer_id),
UNIQUE (manufacturer_id, slug)
```

---

## models (core table)

```sql
id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,

manufacturer_id BIGINT UNSIGNED NOT NULL,
series_id BIGINT UNSIGNED,
category_id BIGINT UNSIGNED,

slug VARCHAR(200) UNIQUE NOT NULL,
name VARCHAR(200) NOT NULL,

production_start_year SMALLINT,
production_end_year SMALLINT,

description TEXT,

horsepower_hp NUMERIC(6,2),

is_active BOOLEAN DEFAULT TRUE,

seo_title VARCHAR(255),
seo_description VARCHAR(255),

name_search TEXT,

created_at TIMESTAMP,
updated_at TIMESTAMP
```

Critical Indexes:

```sql
INDEX idx_models_manufacturer (manufacturer_id),
INDEX idx_models_series (series_id),
INDEX idx_models_category (category_id),
INDEX idx_models_hp (horsepower_hp),
GIN INDEX idx_models_search (name_search gin_trgm_ops)
```

---

## model_specifications (Flexible & Scraper Friendly)

```sql
id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
model_id BIGINT UNSIGNED NOT NULL,

spec_group VARCHAR(120) NOT NULL,
spec_key VARCHAR(160) NOT NULL,
spec_value VARCHAR(255),
unit VARCHAR(40),

display_order SMALLINT DEFAULT 0,

created_at TIMESTAMP,
updated_at TIMESTAMP
```

Indexes:

```sql
INDEX idx_specs_model (model_id),
INDEX idx_specs_group (spec_group),
INDEX idx_specs_key (spec_key)
```

---

## engines

```sql
id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
manufacturer VARCHAR(160),
model VARCHAR(160),
cylinders SMALLINT,
displacement_cc INT,
fuel_type VARCHAR(80),
horsepower_hp NUMERIC(6,2),
cooling_type VARCHAR(80),
aspiration VARCHAR(80)
```

---

## photos

```sql
id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
model_id BIGINT UNSIGNED NOT NULL,
path VARCHAR(255),
alt_text VARCHAR(255),
display_order SMALLINT DEFAULT 0
```

---

# 🔄 Sqids Implementation Pattern

In Model:

```php
use RedExplosion\Sqids\Sqids;

public function getSqidAttribute(): string
{
    return Sqids::encode([$this->id]);
}
```

Route Model Binding:

Create custom binding:

```php
Route::bind('tractor', function ($value) {
    $id = Sqids::decode($value)[0] ?? null;
    return Model::findOrFail($id);
});
```

---

# ⚡ Performance Considerations (INT vs UUID Impact)

| Metric        | UUID   | BIGINT    |
| ------------- | ------ | --------- |
| Index Size    | Large  | Small     |
| Join Speed    | Slower | Faster    |
| Cache Fit     | Poor   | Excellent |
| SEO relevance | None   | None      |

For 500k–2M rows:

BIGINT wins.

---

# 🔎 Search Optimization

Enable pg_trgm:

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

Use:

```sql
WHERE name_search % 'john 1025'
ORDER BY similarity(name_search, 'john 1025') DESC
```

---

# 🐍 Scraper Adjustment for INT IDs

Since we use INT PKs:

The scraper pipeline:

1. Upsert manufacturer by slug
2. Get manufacturer ID
3. Insert series (returning id)
4. Insert model
5. Insert specs

We rely on:

```sql
INSERT ... ON CONFLICT (slug) DO UPDATE
RETURNING id;
```

No UUID generation required.

---

# 🧠 Improved Internal Linking Algorithm

On model page:

Query:

```sql
SELECT id FROM models
WHERE manufacturer_id = ?
AND id != ?
LIMIT 5;
```

Then render via sqid.

Additionally:

```sql
SELECT id FROM models
WHERE horsepower_hp BETWEEN X-5 AND X+5
LIMIT 5;
```

---

# 🏗 Docker Adjustment (No UUID Extensions Needed)

We do NOT need:

* uuid-ossp
* pgcrypto

Simpler Postgres setup.

---

# 🛡 Anti-Enumeration Protection

Sqids alone is not enough.

Also add:

* Rate limiting on model pages
* Block rapid sequential requests
* Detect abnormal pattern in Redis

---

# 🧩 MVP Feature Scope (Updated)

Included:

* INT PKs everywhere
* Sqids in public URLs
* Manufacturer → Series → Model
* Spec rendering
* Search (trigram)
* Redis caching
* Python scraper

---

# 🚀 Future Scalability

If traffic hits:

* 1M+ models
* 10M+ specs

We can:

* Partition model_specifications by model_id range
* Add read replica
* Cache entire model pages statically

---

# 📌 Final Architecture Summary

Backend:

* Laravel 12
* FrankenPHP
* PostgreSQL 18
* Redis

Data:

* INT PK
* Sqids obfuscation
* Trigram search
* GIN indexes

Scraper:

* Python async
* httpx
* selectolax
* asyncpg

Frontend:

* Blade (mostly static)
* Tailwind 4
* Minimal Livewire

Infra:

* Docker
* MinIO
* Redis caching
* Nginx reverse proxy optional

