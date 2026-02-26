# 📘 PRODUCT REQUIREMENTS DOCUMENT (PRD)

## Project: **TractorSpecs (Working Name)**

Clone & Improve Model of **TractorData-style Agricultural Equipment Database**

---

# 1. Executive Summary

Build a structured, SEO-first, database-driven agricultural equipment specification platform similar to TractorData.

Core goal:

> Become the most comprehensive, structured, and SEO-optimized database of tractors and farm equipment specifications.

Primary revenue model:

* Display ads (Ezoic / Mediavine / AdSense)
* Affiliate links (equipment dealers, parts, manuals)
* Sponsored listings (future phase)

This is an **SEO-heavy, content-structured database site**, not a SaaS dashboard.

Stack:

* Laravel 12 + PHP 8.5 (FrankenPHP)
* PostgreSQL 18
* TailwindCSS 4
* Minimal Livewire 4 (admin tools, filtering widgets)
* Redis (caching)
* Docker (Sail + FrankenPHP)
* MinIO / Garage (object storage)
* Python scraper (httpx + selectolax + async)

---

# 2. Competitive Analysis — Structure of TractorData

## 2.1 Site Architecture Pattern

The structure follows strict hierarchical taxonomy:

```
Home
 ├── Manufacturers
 │     ├── John Deere
 │     │     ├── 100 Series
 │     │     │     ├── JD 1023E
 │     │     │     ├── JD 1025R
 │     │
 │     ├── Massey Ferguson
 │
 ├── Categories
 │     ├── Utility Tractors
 │     ├── Compact Tractors
 │     ├── Row Crop Tractors
 │
 ├── Search
 ├── Model Pages
```

### Observations:

1. URL structure is flat and static.
2. Each tractor model = static SEO page.
3. Specs are structured in tabular format.
4. Strong internal linking:

   * Related models
   * Same series
   * Same horsepower range
   * Same manufacturer
5. Content is highly structured (spec fields)
6. Minimal JS
7. Extremely SEO-friendly

---

# 3. Information Architecture (Our Version)

## 3.1 Core Entities

* Manufacturer
* Series
* Model
* Category
* Engine
* Transmission
* Dimensions
* Hydraulics
* Attachments
* Photos
* Documents
* Comparison

---

# 4. Key User Flows

## 4.1 Browse by Manufacturer

User Flow:

Home → Manufacturer → Series → Model → Specs

Goal: Maximize internal linking depth.

---

## 4.2 Browse by Category

Home → Category (Compact Tractors) → Filter → Model → Specs

---

## 4.3 Search

Global search:

* Manufacturer
* Model name
* Horsepower range

---

## 4.4 Compare Tractors (MVP+)

Select 2–3 models → Compare specs side-by-side

---

# 5. Core Pages

---

## 5.1 Home Page

Content Blocks:

* Browse by Manufacturer
* Browse by Category
* Recently Added
* Popular Models
* Search Bar
* Informational content block (SEO intro)

---

## 5.2 Manufacturer Page

URL:

```
/manufacturer/john-deere
```

Sections:

* Description
* List of series
* List of models
* Filter by category
* Internal linking blocks:

  * Popular models
  * Recently updated

---

## 5.3 Series Page

```
/manufacturer/john-deere/100-series
```

Shows:

* All models in series
* Production years
* Quick spec table preview

---

## 5.4 Model Detail Page (Core SEO Page)

```
/tractor/john-deere-1025r
```

## Structure:

* Hero: Name + Production years
* Summary block
* Spec sections:

  * Engine
  * Transmission
  * Hydraulics
  * Dimensions
  * Tires
  * Electrical
* Related Models
* Same HP range
* Same Series
* Comparison CTA
* User Q&A (future)
* Structured Data (Schema.org)

---

# 6. Database Design (PostgreSQL 18)

---

## 6.1 manufacturers

```
id UUID PK
slug VARCHAR UNIQUE
name VARCHAR
description TEXT
country VARCHAR
founded_year INT
logo_path VARCHAR
created_at
updated_at
```

---

## 6.2 categories

```
id UUID
slug
name
description
```

---

## 6.3 series

```
id UUID
manufacturer_id FK
slug
name
production_start_year
production_end_year
```

---

## 6.4 models

```
id UUID
manufacturer_id FK
series_id FK
category_id FK
slug UNIQUE
name
production_start_year
production_end_year
description TEXT
engine_id FK
is_active BOOLEAN
seo_title
seo_description
created_at
updated_at
```

---

## 6.5 engines

```
id UUID
manufacturer
model
cylinders INT
displacement_cc INT
fuel_type
horsepower_hp NUMERIC
torque_nm NUMERIC
cooling_type
aspiration
```

---

## 6.6 transmissions

```
id UUID
type
gears_forward INT
gears_reverse INT
```

---

## 6.7 model_specifications (Flexible)

Key-value structure for extensibility:

```
id UUID
model_id FK
spec_group VARCHAR   (Engine, Hydraulics, etc.)
spec_key VARCHAR
spec_value VARCHAR
unit VARCHAR
display_order INT
```

This allows:

* Easy scraping ingestion
* Flexible additions

---

## 6.8 photos

```
id UUID
model_id FK
path
caption
alt_text
```

---

## 6.9 documents

```
id UUID
model_id FK
type (manual, brochure)
file_path
```

---

## 6.10 comparison_cache

Precomputed comparison HTML cached in Redis.

---

# 7. Scraping & Data Ingestion Strategy

Separate Python service:

### Stack:

* Python 3.13
* httpx (async)
* selectolax (fast HTML parsing)
* asyncio
* tenacity (retry)
* aiolimiter
* postgres async driver (asyncpg)

---

## Scraping Flow

1. Crawl manufacturer list
2. Crawl series pages
3. Crawl model pages
4. Extract:

   * Production years
   * Specs tables
   * Engine details
5. Normalize specs into structured keys

---

## Scraper Architecture

```
crawler/
 ├── fetcher.py (httpx client)
 ├── parser.py (selectolax extraction)
 ├── transformers.py (normalize specs)
 ├── pipeline.py (insert into postgres)
```

---

## Anti-blocking Strategy

* Rotating User Agents
* Proxy pool (optional)
* Rate limit per domain
* Cache HTML snapshots in MinIO
* Respect robots.txt

---

## Data Validation

* Normalize units
* Convert horsepower to numeric
* Remove duplicate specs
* Detect updates via hash comparison

---

# 8. Docker Architecture

Services:

* app (Laravel + FrankenPHP)
* db (Postgres 18)
* redis
* minio
* scraper (python)
* nginx optional (reverse proxy)

---

# 9. Caching Strategy

Redis:

* Model page HTML fragments
* Manufacturer lists
* Popular tractors
* Comparison results

TTL:

* 24 hours

Use cache tags for invalidation.

---

# 10. SEO Strategy (Critical)

---

## 10.1 URL Structure

```
/manufacturer/{slug}
/manufacturer/{slug}/{series}
/tractor/{slug}
/category/{slug}
/compare/{slug1}-vs-{slug2}
```

---

## 10.2 On-Page SEO

Each model page includes:

* H1: Full tractor name
* SEO Title:
  "John Deere 1025R Specs, HP, Reviews (2024)"
* Schema.org Product markup
* Breadcrumbs
* Internal links (10+ per page)

---

## 10.3 Internal Linking Blueprint

Each model page auto-links:

* Same manufacturer (5 models)
* Same series
* Same horsepower range
* Same category

Target:

> 15–25 internal links per model page.

---

## 10.4 Programmatic SEO Pages (MVP+)

Auto-generate pages:

* "Tractors under 50 HP"
* "4WD tractors 2015"
* "John Deere tractors 30-40 HP"

---

## 10.5 Link Building

Phase 1:

* Farm forums
* Equipment blogs
* Reddit agriculture communities

Phase 2:

* Guest posts
* Manufacturer outreach
* Data citation strategy

---

# 11. Performance Strategy

* Static Blade rendering
* No SPA
* No heavy JS
* Redis full-page caching (optional)
* Postgres trigram search

Indexes:

* slug indexes
* manufacturer_id
* GIN index on search fields

---

# 12. Admin Panel

Use Livewire 4 sparingly:

* Model editor
* Spec editor
* Bulk importer
* Scraper status dashboard

---

# 13. Engagement Enhancements (Phase 2)

* Tractor comparison tool
* User ratings
* Tractor marketplace
* Saved tractors
* Email alerts
* "Similar tractors to X"
* Price trend graphs
* Horsepower calculator

---

# 14. Monetization

MVP:

* Display ads
* Affiliate links (equipment dealers)

Future:

* Premium API access
* Lead generation for dealers
* Sponsored placements

---

# 15. MVP Scope (Strict)

Included:

* Manufacturer
* Series
* Model
* Spec sections
* Search
* Internal linking
* Basic admin
* Scraper
* SEO meta

Excluded:

* User accounts
* Reviews
* Marketplace
* API
* Complex filters
* Analytics dashboards

---

# 16. Success Metrics

First 6 months:

* 5,000 indexed pages
* 100K monthly visitors
* 2–3 min avg session time
* 15+ internal links per page
* 1M+ impressions in GSC

---

# 17. Long-Term Advantage Strategy

1. Normalize specs better than competitors.
2. Add comparison engine.
3. Add attachments database.
4. Add structured filtering.
5. Add programmatic SEO pages.

---

# 18. Implementation Order

Phase 1:

* DB schema
* Manufacturer → Model rendering
* SEO meta
* Basic search

Phase 2:

* Scraper pipeline
* Caching
* Comparison

Phase 3:

* Programmatic pages
* Engagement features

---

# 19. Why This Can Work for a Solo Founder

* Mostly static content
* High SEO leverage
* Long-tail traffic
* Low infra cost
* Evergreen niche
* Easy scraping structure
* Clear data model

