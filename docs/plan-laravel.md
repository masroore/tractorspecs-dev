# 🚜 Laravel Web App Implementation Plan

**Stack:** Laravel 12 · PHP 8.5 · FrankenPHP · PostgreSQL 18 · Redis · Livewire 4 · Flux UI Pro · TailwindCSS 4 · Laravel Sail · Pest 4

---

## Overview

A static-first, SEO-optimized tractor specification database. All public pages are rendered with Blade server-side — no Livewire or JavaScript on the frontend. Livewire 4 + Flux UI Pro is used exclusively for the admin panel. Redis caches full page fragments with tag-based invalidation. Sqids obfuscate internal IDs in admin URLs. pg_trgm powers fuzzy full-text search.

**Key decisions:**
- BIGINT PKs everywhere (not UUIDs) — per addendum-1, faster joins, smaller indexes
- `red-explosion/laravel-sqids` for public URL obfuscation in admin/API — public SEO pages use clean slugs only
- Blade-only public pages — no Livewire on frontend, minimal JS overhead, maximum SEO/crawlability
- Livewire 4 + Flux UI Pro for admin panel only
- Redis tag-based cache invalidation — instant consistency when admin edits a model
- GIN trigram indexes + `pg_trgm` for fuzzy search
- `TractorModel` model name — avoids PHP collision with `Illuminate\Database\Eloquent\Model`
- Fortify for admin auth — headless, no extra UI bloat

---

## Phase 1: Foundation & Database

### Step 1 — Project Bootstrap

If starting from scratch:
```bash
curl -s https://laravel.build/tractorspecs | bash
cd tractorspecs
vendor/bin/sail up -d
```

Install required packages:
```bash
vendor/bin/sail composer require red-explosion/laravel-sqids
vendor/bin/sail composer require laravel/fortify
vendor/bin/sail composer require livewire/livewire livewire/flux
```

Configure `.env`:
```
DB_CONNECTION=pgsql
DB_HOST=pgsql
DB_PORT=5432
DB_DATABASE=tractorspecs
CACHE_DRIVER=redis
SESSION_DRIVER=redis
QUEUE_CONNECTION=redis
```

Publish Fortify config:
```bash
vendor/bin/sail artisan vendor:publish --provider="Laravel\Fortify\FortifyServiceProvider" --no-interaction
```

---

### Step 2 — Enable pg_trgm Extension

**File:** `database/migrations/0001_01_01_000000_enable_pg_trgm.php`

Must run before all other migrations. Use `DB::statement`:

```php
public function up(): void
{
    DB::statement('CREATE EXTENSION IF NOT EXISTS pg_trgm');
}

public function down(): void
{
    DB::statement('DROP EXTENSION IF EXISTS pg_trgm');
}
```

---

### Step 3 — Database Migrations

Create each via `vendor/bin/sail artisan make:migration --no-interaction`. Run in the order listed. All IDs are BIGINT UNSIGNED auto-increment per addendum-1.

#### `create_manufacturers_table`

Columns:
- `id` — `$table->id()` (BIGINT UNSIGNED auto-increment PK)
- `slug` — `$table->string('slug', 160)->unique()`
- `name` — `$table->string('name', 160)`
- `country` — `$table->string('country', 120)->nullable()`
- `founded_year` — `$table->smallInteger('founded_year')->nullable()`
- `description` — `$table->text('description')->nullable()`
- `logo_path` — `$table->string('logo_path', 255)->nullable()`
- `name_search` — `$table->text('name_search')->nullable()`
- `$table->timestamps()`

Extra indexes via raw statements:
```php
DB::statement("CREATE INDEX idx_manufacturers_name_search ON manufacturers USING GIN (name_search gin_trgm_ops)");
```

#### `create_categories_table`

Columns: `id`, `slug` VARCHAR(160) UNIQUE, `name` VARCHAR(160), `description` TEXT nullable, timestamps.

#### `create_series_table`

Columns:
- `id`
- `manufacturer_id` — `$table->foreignId('manufacturer_id')->constrained()->cascadeOnDelete()`
- `slug` — `$table->string('slug', 160)`
- `name` — `$table->string('name', 160)`
- `production_start_year` — `$table->smallInteger()->nullable()`
- `production_end_year` — `$table->smallInteger()->nullable()`
- timestamps

Constraints:
```php
$table->unique(['manufacturer_id', 'slug']);
$table->index('manufacturer_id');
```

#### `create_engines_table`

Columns:
- `id`
- `manufacturer` — VARCHAR(160) nullable
- `model` — VARCHAR(160) nullable
- `cylinders` — `$table->smallInteger()->nullable()`
- `displacement_cc` — `$table->integer()->nullable()`
- `fuel_type` — VARCHAR(80) nullable
- `horsepower_hp` — `$table->decimal('horsepower_hp', 6, 2)->nullable()`
- `cooling_type` — VARCHAR(80) nullable
- `aspiration` — VARCHAR(80) nullable

No timestamps (static reference data).

#### `create_tractor_models_table`

Columns:
- `id`
- `manufacturer_id` — FK → manufacturers, cascade delete
- `series_id` — FK → series, nullable, set null on delete
- `category_id` — FK → categories, nullable, set null on delete
- `slug` — VARCHAR(200) UNIQUE
- `name` — VARCHAR(200)
- `production_start_year` — SMALLINT nullable
- `production_end_year` — SMALLINT nullable
- `description` — TEXT nullable
- `horsepower_hp` — NUMERIC(6,2) nullable
- `is_active` — BOOLEAN DEFAULT TRUE
- `seo_title` — VARCHAR(255) nullable
- `seo_description` — VARCHAR(255) nullable
- `name_search` — TEXT nullable
- timestamps

Indexes:
```php
$table->index('manufacturer_id');
$table->index('series_id');
$table->index('category_id');
$table->index('horsepower_hp');
```
GIN index via raw statement:
```php
DB::statement("CREATE INDEX idx_models_name_search ON tractor_models USING GIN (name_search gin_trgm_ops)");
```

#### `create_model_specifications_table`

Columns:
- `id`
- `model_id` — FK → tractor_models, cascade delete
- `spec_group` — VARCHAR(120)
- `spec_key` — VARCHAR(160)
- `spec_value` — VARCHAR(255) nullable
- `unit` — VARCHAR(40) nullable
- `display_order` — SMALLINT DEFAULT 0
- timestamps

Indexes: `model_id`, `spec_group`, `spec_key`.

#### `create_photos_table`

Columns:
- `id`
- `model_id` — FK → tractor_models, cascade delete
- `path` — VARCHAR(255)
- `alt_text` — VARCHAR(255) nullable
- `display_order` — SMALLINT DEFAULT 0

---

### Step 4 — Eloquent Models

Create via `vendor/bin/sail artisan make:model --no-interaction`. All in `app/Models/`.

#### `app/Models/Manufacturer.php`

```php
protected $fillable = ['slug', 'name', 'country', 'founded_year', 'description', 'logo_path', 'name_search'];

protected function casts(): array
{
    return [
        'founded_year' => 'integer',
    ];
}

public function series(): HasMany
{
    return $this->hasMany(Series::class);
}

public function tractorModels(): HasMany
{
    return $this->hasMany(TractorModel::class);
}

public function getSqidAttribute(): string
{
    return Sqids::encode([$this->id]);
}

public function scopeSearch(Builder $query, string $term): Builder
{
    return $query
        ->whereRaw('name_search % ?', [$term])
        ->orderByRaw('similarity(name_search, ?) DESC', [$term]);
}
```

#### `app/Models/TractorModel.php`

```php
protected $table = 'tractor_models';
protected $fillable = ['manufacturer_id', 'series_id', 'category_id', 'slug', 'name',
    'production_start_year', 'production_end_year', 'description',
    'horsepower_hp', 'is_active', 'seo_title', 'seo_description', 'name_search'];

protected function casts(): array
{
    return [
        'horsepower_hp'         => 'float',
        'is_active'             => 'boolean',
        'production_start_year' => 'integer',
        'production_end_year'   => 'integer',
    ];
}

public function manufacturer(): BelongsTo { return $this->belongsTo(Manufacturer::class); }
public function series(): BelongsTo { return $this->belongsTo(Series::class); }
public function category(): BelongsTo { return $this->belongsTo(Category::class); }
public function specifications(): HasMany { return $this->hasMany(ModelSpecification::class, 'model_id'); }
public function photos(): HasMany { return $this->hasMany(Photo::class, 'model_id'); }

public function getSqidAttribute(): string { return Sqids::encode([$this->id]); }

public function scopeActive(Builder $query): Builder
{
    return $query->where('is_active', true);
}

public function scopeSearch(Builder $query, string $term): Builder
{
    return $query
        ->whereRaw('name_search % ?', [$term])
        ->orderByRaw('similarity(name_search, ?) DESC', [$term]);
}

public function scopeSimilarHp(Builder $query, float $hp, int $range = 5): Builder
{
    return $query->whereBetween('horsepower_hp', [$hp - $range, $hp + $range]);
}
```

#### `app/Models/Series.php`

Relationships: `belongsTo(Manufacturer::class)`, `hasMany(TractorModel::class)`. Sqid accessor.

#### `app/Models/Category.php`

Relationship: `hasMany(TractorModel::class)`.

#### `app/Models/ModelSpecification.php`

```php
protected $table = 'model_specifications';
protected $fillable = ['model_id', 'spec_group', 'spec_key', 'spec_value', 'unit', 'display_order'];

public function tractorModel(): BelongsTo { return $this->belongsTo(TractorModel::class, 'model_id'); }

public function scopeForGroup(Builder $query, string $group): Builder
{
    return $query->where('spec_group', $group)->orderBy('display_order');
}
```

#### `app/Models/Engine.php`, `app/Models/Photo.php`

Standard fillable + relationships per schema.

---

### Step 5 — Factories & Seeders

Create factories via `vendor/bin/sail artisan make:factory --no-interaction`.

#### `ManufacturerFactory`

Realistic names: John Deere, Massey Ferguson, Kubota, New Holland, Case IH, Fendt, AGCO, Deutz-Fahr. Generate valid slugs from name. Random country, founded_year 1840–1970.

#### `TractorModelFactory`

- HP: `fake()->randomFloat(2, 15, 250)`
- Production years: start 1960–2015, end start+1 to start+20 or null (current production)
- Slug from name
- States: `active()`, `inactive()`

#### `ModelSpecificationFactory`

Spec groups: `Engine`, `Transmission`, `Hydraulics`, `Dimensions`, `Tires`, `Electrical`.
Sample keys per group e.g. Engine: Cylinders, Displacement, Fuel Type, HP, Cooling.

#### `DatabaseSeeder`

```php
public function run(): void
{
    Manufacturer::factory(8)->create()->each(function (Manufacturer $manufacturer) {
        Series::factory(3)->create(['manufacturer_id' => $manufacturer->id])->each(
            function (Series $series) use ($manufacturer) {
                TractorModel::factory(8)->create([
                    'manufacturer_id' => $manufacturer->id,
                    'series_id' => $series->id,
                ])->each(fn (TractorModel $model) =>
                    ModelSpecification::factory(15)->create(['model_id' => $model->id])
                );
            }
        );
    });
}
```

---

## Phase 2: Routing & Controllers

### Step 6 — Route Definitions

**File:** `routes/web.php`

```php
// Public routes
Route::get('/', [HomeController::class, 'index'])->name('home');
Route::get('search', [SearchController::class, 'index'])->name('search');

Route::prefix('manufacturer')->name('manufacturer.')->group(function () {
    Route::get('/', [ManufacturerController::class, 'index'])->name('index');
    Route::get('{slug}', [ManufacturerController::class, 'show'])->name('show');
    Route::get('{manufacturerSlug}/{seriesSlug}', [SeriesController::class, 'show'])
        ->name('series.show');
});

Route::get('category/{slug}', [CategoryController::class, 'show'])->name('category.show');
Route::get('tractor/{slug}', [TractorModelController::class, 'show'])->name('tractor.show');
Route::get('compare/{slug1}-vs-{slug2}', [CompareController::class, 'show'])->name('compare.show');

// Admin routes
Route::prefix('admin')->name('admin.')->middleware(['auth', 'verified'])->group(function () {
    Route::get('/', [AdminDashboardController::class, 'index'])->name('dashboard');
    Route::get('manufacturers', ManufacturerManager::class)->name('manufacturers');
    Route::get('models', ModelManager::class)->name('models');
    Route::get('models/{model}/specs', SpecEditor::class)->name('specs');
    Route::get('scraper', ScraperStatus::class)->name('scraper');
    Route::get('import', BulkImport::class)->name('import');
});

// Auth routes (Fortify handles POST endpoints automatically)
Route::get('login', [AuthController::class, 'showLogin'])->name('login');
Route::get('logout', [AuthController::class, 'logout'])->name('logout');
```

---

### Step 7 — Controllers

Create via `vendor/bin/sail artisan make:controller --no-interaction`.

#### `HomeController`

```php
public function index(): View
{
    return Cache::tags(['home'])->remember('home.index', 86400, function () {
        $manufacturers = Manufacturer::query()->orderBy('name')->get();
        $categories    = Category::query()->orderBy('name')->get();
        $recentModels  = TractorModel::query()->active()->latest()->limit(12)->get();
        $popularModels = TractorModel::query()->active()->inRandomOrder()->limit(12)->get();
        return view('home', compact('manufacturers', 'categories', 'recentModels', 'popularModels'));
    });
}
```

Note: `Cache::remember` with `View` return — store the view data, not the rendered HTML, to avoid Blade serialization issues. Alternatively cache the rendered string.

#### `ManufacturerController`

- `index()`: `Manufacturer::query()->orderBy('name')->get()`, cached under `['manufacturers']` tag for 24h.
- `show(string $slug)`: find by slug or 404; eager-load `series`, `tractorModels` (latest 20, active); build breadcrumb; cache under `['manufacturer', "manufacturer.{$manufacturer->id}"]`.

#### `SeriesController`

- `show(string $manufacturerSlug, string $seriesSlug)`: find manufacturer then series or 404; eager-load `tractorModels` (with manufacturer, category); breadcrumb data; cache per series.

#### `TractorModelController`

```php
public function show(string $slug): View
{
    $model = Cache::tags(['model', "model.slug.{$slug}"])->remember(
        "tractor.show.{$slug}", 86400,
        function () use ($slug) {
            return TractorModel::query()
                ->with(['manufacturer', 'series', 'category', 'photos',
                        'specifications' => fn ($q) => $q->orderBy('spec_group')->orderBy('display_order')])
                ->where('slug', $slug)
                ->active()
                ->firstOrFail();
        }
    );

    $groupedSpecs    = $model->specifications->groupBy('spec_group');
    $relatedModels   = $this->relatedModelsService->getRelatedByManufacturer($model);
    $similarHpModels = $this->relatedModelsService->getRelatedByHp($model);
    $seriesModels    = $this->relatedModelsService->getRelatedBySeries($model);

    $seoTitle       = $model->seo_title
        ?? "{$model->name} Specs, HP & Reviews ({$model->production_start_year})";
    $seoDescription = $model->seo_description
        ?? "Full specifications for the {$model->name}: engine, transmission, hydraulics, and dimensions.";
    $canonicalUrl   = route('tractor.show', $model->slug);

    return view('tractor.show', compact(
        'model', 'groupedSpecs', 'relatedModels', 'similarHpModels', 'seriesModels',
        'seoTitle', 'seoDescription', 'canonicalUrl'
    ));
}
```

Constructor-inject `RelatedModelsService`.

#### `SearchController`

- Validate `q` min:2, max:100
- Delegate to `SearchService::search($term)`
- Paginate results (20/page)
- No caching — dynamic per query
- Return `view('search.index', compact('models', 'manufacturers', 'term'))`

#### `CategoryController`

- Find category by slug or 404
- Paginate active models in category (24/page)
- Cache per slug + page number

#### `CompareController`

- Load both models by slug or 404
- Cache key: sorted slugs `compare.` . implode('-vs-', sort([$slug1, $slug2]))
- Pass both models + their specs to `compare.show` view

#### `AdminDashboardController`

- Stats: total manufacturers, total models, total specs, pending crawl targets count
- Return admin dashboard view

---

### Step 8 — Services

Create via `vendor/bin/sail artisan make:class --no-interaction`.

#### `app/Services/RelatedModelsService.php`

```php
public function getRelatedByManufacturer(TractorModel $model, int $limit = 5): Collection
{
    return TractorModel::query()
        ->where('manufacturer_id', $model->manufacturer_id)
        ->where('id', '!=', $model->id)
        ->active()
        ->inRandomOrder()
        ->limit($limit)
        ->get();
}

public function getRelatedByHp(TractorModel $model, int $range = 5, int $limit = 5): Collection
{
    if (! $model->horsepower_hp) {
        return collect();
    }

    return TractorModel::query()
        ->similarHp($model->horsepower_hp, $range)
        ->where('id', '!=', $model->id)
        ->active()
        ->limit($limit)
        ->get();
}

public function getRelatedBySeries(TractorModel $model, int $limit = 5): Collection
{
    if (! $model->series_id) {
        return collect();
    }

    return TractorModel::query()
        ->where('series_id', $model->series_id)
        ->where('id', '!=', $model->id)
        ->active()
        ->limit($limit)
        ->get();
}
```

#### `app/Services/SearchService.php`

```php
public function search(string $term): array
{
    $models = TractorModel::query()
        ->active()
        ->search($term)
        ->with('manufacturer')
        ->limit(20)
        ->get();

    $manufacturers = Manufacturer::query()
        ->search($term)
        ->limit(5)
        ->get();

    return compact('models', 'manufacturers');
}
```

#### `app/Services/CacheService.php`

```php
public function invalidateManufacturer(int $id): void
{
    Cache::tags(['manufacturer', "manufacturer.{$id}"])->flush();
    Cache::tags(['home'])->flush();
}

public function invalidateModel(int $id, string $slug): void
{
    Cache::tags(['model', "model.{$id}", "model.slug.{$slug}"])->flush();
}

public function invalidateHome(): void
{
    Cache::tags(['home'])->flush();
}
```

---

### Step 9 — Model Observers

Create via `vendor/bin/sail artisan make:observer --no-interaction`.

#### `ManufacturerObserver`

On `updated` and `deleted`: call `CacheService::invalidateManufacturer($manufacturer->id)`.

#### `TractorModelObserver`

On `updated` and `deleted`: call `CacheService::invalidateModel($model->id, $model->slug)`.

Register both in `AppServiceProvider::boot()`.

---

## Phase 3: Views & SEO

### Step 10 — Blade Layout

**File:** `resources/views/layouts/app.blade.php`

Structure:
```html
<!DOCTYPE html>
<html lang="{{ str_replace('_', '-', app()->getLocale()) }}">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>@yield('title', config('app.name'))</title>
    <meta name="description" content="@yield('description')">
    <link rel="canonical" href="@yield('canonical')">
    @yield('og-meta')
    @yield('schema')
    @vite(['resources/css/app.css', 'resources/js/app.js'])
</head>
<body class="bg-white text-gray-900 antialiased">
    @include('partials.nav')
    <main>@yield('content')</main>
    @include('partials.footer')
    @livewireScripts
</body>
</html>
```

**File:** `resources/views/layouts/admin.blade.php`

Flux UI Pro sidebar layout:
```blade
<flux:sidebar>
    <flux:navlist>
        <flux:navlist.item href="{{ route('admin.dashboard') }}" icon="home">Dashboard</flux:navlist.item>
        <flux:navlist.item href="{{ route('admin.manufacturers') }}" icon="building-office">Manufacturers</flux:navlist.item>
        <flux:navlist.item href="{{ route('admin.models') }}" icon="truck">Models</flux:navlist.item>
        <flux:navlist.item href="{{ route('admin.scraper') }}" icon="cpu-chip">Scraper</flux:navlist.item>
        <flux:navlist.item href="{{ route('admin.import') }}" icon="arrow-up-tray">Import</flux:navlist.item>
    </flux:navlist>
</flux:sidebar>
```

---

### Step 11 — Blade Components

Create via `vendor/bin/sail artisan make:component --no-interaction`:

#### `<x-breadcrumb :items="$items" />`

`$items` is an array of `['label' => string, 'url' => string|null]`. Renders Schema.org BreadcrumbList JSON-LD inline + visible `<nav aria-label="Breadcrumb">` with `≫` separators.

#### `<x-spec-table :specs="$specs" :group="$group" />`

Renders a labeled spec group as a `<table>` with key/value rows. Unit shown after value if present.

#### `<x-model-card :model="$model" />`

Card showing: name, manufacturer name, production years, HP badge, link to tractor show page.

#### `<x-manufacturer-card :manufacturer="$manufacturer" />`

Card showing: logo (if exists), name, country, model count.

#### `<x-seo-meta :title :description :canonical />`

Outputs `<title>`, `<meta name="description">`, `<link rel="canonical">`, Open Graph `og:title`, `og:description`, `og:url` meta tags.

#### `<x-schema-product :model="$model" />`

Outputs `<script type="application/ld+json">` block:
```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "John Deere 1025R",
  "description": "...",
  "brand": { "@type": "Brand", "name": "John Deere" },
  "additionalProperty": [
    { "@type": "PropertyValue", "name": "Horsepower", "value": "25 HP" },
    { "@type": "PropertyValue", "name": "Engine Cylinders", "value": "3" }
  ]
}
```
Populates `additionalProperty` from model's `specifications` relationship (eager-loaded).

#### `<x-internal-links :models :title />`

Renders a titled grid of `<x-model-card>` components. Used for related models sections at bottom of tractor page.

#### `<x-hero-bar :name :years :hp />`

Renders H1 with model name, production years badge, HP badge.

---

### Step 12 — Core Views

#### `resources/views/home.blade.php`
- `@extends('layouts.app')`
- Browse by Manufacturer: responsive grid of `<x-manufacturer-card>`
- Browse by Category: grid of category tiles
- Recently Added models: 3-column card grid
- SEO intro paragraph (static copy referencing the site's purpose)
- `@livewire('search-widget')` in nav area

#### `resources/views/manufacturer/index.blade.php`
- Alphabetical groups with letter anchor links
- Each manufacturer as `<x-manufacturer-card>`

#### `resources/views/manufacturer/show.blade.php`
- `<x-breadcrumb>` — Home > Manufacturers > {name}
- Manufacturer hero: name, country, founded year
- Description text
- Series list: each series links to series page, shows model count
- Recent models grid (latest 12)

#### `resources/views/manufacturer/series.blade.php`
- `<x-breadcrumb>` — Home > {Manufacturer} > {Series}
- Series name + production year range as H1
- All models in series as `<x-model-card>` grid

#### `resources/views/tractor/show.blade.php`

Structure:
```blade
@section('schema')
    <x-schema-product :model="$model" />
@endsection

@section('content')
    <x-breadcrumb :items="$breadcrumbs" />
    <x-hero-bar :name="$model->name" :years="..." :hp="$model->horsepower_hp" />

    @if($model->description)
        <p class="...">{{ $model->description }}</p>
    @endif

    @foreach($groupedSpecs as $group => $specs)
        <x-spec-table :specs="$specs" :group="$group" />
    @endforeach

    @if($model->photos->isNotEmpty())
        {{-- photo gallery --}}
    @endif

    <x-internal-links :models="$relatedModels" title="More from {{ $model->manufacturer->name }}" />
    <x-internal-links :models="$similarHpModels" title="Similar Horsepower ({{ $model->horsepower_hp }} HP)" />
    <x-internal-links :models="$seriesModels" title="Same Series" />

    <a href="{{ route('compare.show', ...) }}" class="...">Compare with another tractor</a>
@endsection
```

#### `resources/views/search/index.blade.php`
- GET search form (standard HTML, no Livewire)
- Manufacturer results section (5 max)
- Model results section (20, paginated)
- Empty state when no results

#### `resources/views/compare/show.blade.php`
- Side-by-side table layout
- Spec rows: highlight differing values in amber, matching values in neutral
- Back links to each tractor's individual page

---

### Step 13 — SEO & Sitemap

#### Sitemap Command

Create via `vendor/bin/sail artisan make:command GenerateSitemap --no-interaction`.

**File:** `app/Console/Commands/GenerateSitemap.php`

```php
#[AsCommand(name: 'app:generate-sitemap')]
class GenerateSitemap extends Command
{
    public function handle(): int
    {
        $urls = collect();

        Manufacturer::query()->cursor()->each(fn ($m) =>
            $urls->push(route('manufacturer.show', $m->slug))
        );

        Series::query()->with('manufacturer')->cursor()->each(fn ($s) =>
            $urls->push(route('manufacturer.series.show', [$s->manufacturer->slug, $s->slug]))
        );

        TractorModel::query()->active()->cursor()->each(fn ($m) =>
            $urls->push(route('tractor.show', $m->slug))
        );

        Category::query()->cursor()->each(fn ($c) =>
            $urls->push(route('category.show', $c->slug))
        );

        $xml = view('sitemap', ['urls' => $urls])->render();
        file_put_contents(public_path('sitemap.xml'), $xml);

        $this->info("Sitemap generated with {$urls->count()} URLs.");
        return self::SUCCESS;
    }
}
```

Schedule in `routes/console.php`:
```php
Schedule::command('app:generate-sitemap')->weekly();
```

---

## Phase 4: Livewire Admin Panel

### Step 14 — Admin Authentication

Configure `config/fortify.php`:
```php
'features' => [
    Features::emailVerification(),
    Features::resetPasswords(),
],
'home' => '/admin',
'guard' => 'web',
```

Create login view at `resources/views/auth/login.blade.php` using Flux UI form components.

Protect all `/admin/*` routes with `auth` middleware — registered in `bootstrap/app.php`:
```php
->withMiddleware(function (Middleware $middleware) {
    $middleware->web(append: [
        // any global web middleware
    ]);
})
```

---

### Step 15 — Livewire Admin Components

Create via `vendor/bin/sail artisan make:livewire --no-interaction`.

#### `ManufacturerManager` (`app/Livewire/Admin/ManufacturerManager.php`)

Properties: `$search`, `$editingId`, `$name`, `$country`, `$description`

Actions:
- `updatedSearch()` — resets pagination
- `edit(int $id)` — loads manufacturer into form fields
- `save()` — validates + updates + flushes cache + shows Flux toast
- `delete(int $id)` — soft-confirm modal, delete, flush cache

View: `<flux:table>` with search `<flux:input>`, edit/delete per row.

#### `ModelManager` (`app/Livewire/Admin/ModelManager.php`)

Properties: `$search`, `$manufacturerFilter`, `$categoryFilter`, `$activeFilter`

Actions:
- `toggleActive(int $id)` — flip is_active, flush cache
- `updatedFilters()` — reset pagination

View: filterable sortable `<flux:table>` with link to spec editor per row.

#### `SpecEditor` (`app/Livewire/Admin/SpecEditor.php`)

Mount: load `TractorModel` by ID, load all specs into `$specs` array.

```php
public function mount(TractorModel $model): void
{
    $this->model  = $model;
    $this->specs  = $model->specifications()
        ->orderBy('spec_group')
        ->orderBy('display_order')
        ->get()
        ->toArray();
}
```

Actions:
- `addSpec()` — push empty row to `$specs`
- `removeSpec(int $index)` — unset row
- `saveSpecs()` — validate, delete all, re-insert, flush model cache, Flux toast success
- `reorderSpecs()` — accept new `display_order` values from drag-drop

#### `ScraperStatus` (`app/Livewire/Admin/ScraperStatus.php`)

Mount: query `crawl_targets` for counts by status. Poll every 10s via `#[Poll(10000)]` attribute.

Properties: `$pendingCount`, `$doneCount`, `$failedCount`, `$failedTargets`

Actions:
- `retryFailed()` — `UPDATE crawl_targets SET status='pending' WHERE status='failed'`, dispatch toast

View: progress bars, stats cards, failed targets table with error messages.

#### `BulkImport` (`app/Livewire/Admin/BulkImport.php`)

Properties: `$csvFile`, `$preview`, `$mapping`, `$importStatus`

Actions:
- `updatedCsvFile()` — parse first 5 rows for preview
- `import()` — validate mapping, dispatch `ImportModelsCsvJob` (queued), show progress

#### `SearchWidget` (`app/Livewire/SearchWidget.php`) — public-facing

```php
public string $query = '';
public array $results = [];

#[On('search')]
public function updatedQuery(): void
{
    if (strlen($this->query) < 2) {
        $this->results = [];
        return;
    }
    $this->results = TractorModel::query()
        ->active()
        ->search($this->query)
        ->with('manufacturer')
        ->limit(5)
        ->get()
        ->toArray();
}
```

Wire directive: `wire:model.live.debounce.300ms="query"`.
On submit: redirect to `route('search', ['q' => $this->query])`.

---

## Phase 5: Performance & Caching

### Step 16 — Redis Configuration

**File:** `config/database.php` (redis section)

Configure separate Redis databases:
- DB 0: cache (`REDIS_CACHE_DB=0`)
- DB 1: sessions (`REDIS_SESSION_DB=1`)
- DB 2: queues (`REDIS_QUEUE_DB=2`)

**File:** `.env`

```
REDIS_HOST=redis
REDIS_PORT=6379
CACHE_STORE=redis
SESSION_DRIVER=redis
QUEUE_CONNECTION=redis
```

### Cache Tag Strategy

| Cache Tag | Invalidated when |
|-----------|-----------------|
| `home` | Any manufacturer or popular model changes |
| `manufacturers` | Any manufacturer created/updated/deleted |
| `manufacturer.{id}` | That specific manufacturer updated/deleted |
| `model.{id}` | That model updated/deleted |
| `model.slug.{slug}` | That model updated/deleted |
| `series.{id}` | That series or any of its models updated |
| `category.{slug}` | Any model in that category updated |

---

### Step 17 — Query Optimization

Ensure all controller queries eager-load relationships to prevent N+1:

```php
// Good — single query per relationship
TractorModel::query()
    ->with(['manufacturer', 'series', 'specifications', 'photos'])
    ->where('slug', $slug)
    ->firstOrFail();

// Bad — N+1
$model = TractorModel::where('slug', $slug)->first();
echo $model->manufacturer->name; // extra query per model
```

Add `protected $with = []` to models only for universally-needed relationships. Prefer explicit eager loading per controller action.

---

## Phase 6: Testing

### Step 18 — Feature Tests

Create via `vendor/bin/sail artisan make:test --pest --no-interaction`.

#### `tests/Feature/HomePageTest.php`

```php
it('renders home page', function () {
    Manufacturer::factory(3)->create();
    TractorModel::factory(5)->active()->create();

    get(route('home'))->assertOk()->assertViewHas('manufacturers');
});

it('caches home page on second request', function () {
    get(route('home'));
    get(route('home')); // should hit cache
    // Assert DB query count is lower on second request
});
```

#### `tests/Feature/ManufacturerPageTest.php`

```php
it('renders manufacturer index', fn () =>
    get(route('manufacturer.index'))->assertOk()
);

it('renders manufacturer show page', function () {
    $manufacturer = Manufacturer::factory()->create();

    get(route('manufacturer.show', $manufacturer->slug))
        ->assertOk()
        ->assertSee($manufacturer->name);
});

it('returns 404 for unknown manufacturer slug', fn () =>
    get(route('manufacturer.show', 'nonexistent-manufacturer'))->assertNotFound()
);
```

#### `tests/Feature/TractorModelPageTest.php`

```php
it('renders tractor model detail page', function () {
    $model = TractorModel::factory()
        ->has(ModelSpecification::factory(10), 'specifications')
        ->active()
        ->create();

    get(route('tractor.show', $model->slug))
        ->assertOk()
        ->assertSee($model->name)
        ->assertSee($model->manufacturer->name);
});

it('includes schema.org JSON-LD in output', function () {
    $model = TractorModel::factory()->active()->create();
    get(route('tractor.show', $model->slug))
        ->assertOk()
        ->assertSee('application/ld+json', false);
});

it('returns 404 for inactive model', function () {
    $model = TractorModel::factory()->inactive()->create();
    get(route('tractor.show', $model->slug))->assertNotFound();
});

it('returns 404 for unknown slug', fn () =>
    get(route('tractor.show', 'nonexistent-slug'))->assertNotFound()
);
```

#### `tests/Feature/SearchTest.php`

```php
it('returns results for valid query', function () {
    TractorModel::factory()->active()->create(['name' => 'John Deere 1025R']);

    get(route('search', ['q' => 'john']))->assertOk()->assertSee('John Deere 1025R');
});

it('returns empty state for no results', function () {
    get(route('search', ['q' => 'xyznotamodel']))->assertOk()->assertSee('No results');
});

it('validates query minimum length', fn () =>
    get(route('search', ['q' => 'x']))->assertRedirect()
);
```

#### `tests/Feature/ComparePageTest.php`

```php
it('renders compare page for two valid tractors', function () {
    [$a, $b] = TractorModel::factory(2)->active()->create();
    get(route('compare.show', ['slug1' => $a->slug, 'slug2' => $b->slug]))->assertOk();
});
```

#### `tests/Feature/Admin/AdminAccessTest.php`

```php
it('redirects unauthenticated users from admin', fn () =>
    get(route('admin.dashboard'))->assertRedirect(route('login'))
);

it('renders admin dashboard for authenticated user', function () {
    $user = User::factory()->create();
    actingAs($user)->get(route('admin.dashboard'))->assertOk();
});
```

#### `tests/Feature/Admin/ManufacturerManagerTest.php`

```php
it('can search manufacturers in admin', function () {
    $user = User::factory()->create();
    Manufacturer::factory()->create(['name' => 'John Deere']);

    Livewire::actingAs($user)
        ->test(ManufacturerManager::class)
        ->set('search', 'John')
        ->assertSee('John Deere');
});

it('can update manufacturer name', function () {
    $user = User::factory()->create();
    $manufacturer = Manufacturer::factory()->create();

    Livewire::actingAs($user)
        ->test(ManufacturerManager::class)
        ->call('edit', $manufacturer->id)
        ->set('name', 'Updated Name')
        ->call('save')
        ->assertHasNoErrors();

    expect($manufacturer->fresh()->name)->toBe('Updated Name');
});
```

#### `tests/Feature/SitemapTest.php`

```php
it('generates sitemap with active model URLs', function () {
    TractorModel::factory(3)->active()->create();

    artisan('app:generate-sitemap')->assertOk();
    expect(file_exists(public_path('sitemap.xml')))->toBeTrue();
    expect(file_get_contents(public_path('sitemap.xml')))->toContain('<urlset');
});
```

---

## Phase 7: Docker & Deployment

### Step 19 — docker-compose.yml Services

```yaml
services:
  laravel.test:
    build:
      context: ./vendor/laravel/sail/runtimes/8.5
      dockerfile: Dockerfile
    image: sail-8.5/app
    ports:
      - '${APP_PORT:-80}:80'
    environment:
      WWWUSER: '${WWWUSER}'
      LARAVEL_SAIL: 1
    volumes:
      - '.:/var/www/html'
    networks:
      - sail
    depends_on:
      - pgsql
      - redis
      - minio

  pgsql:
    image: 'postgres:18-alpine'
    ports:
      - '${FORWARD_DB_PORT:-5432}:5432'
    environment:
      PGPASSWORD: '${DB_PASSWORD:-secret}'
      POSTGRES_DB: '${DB_DATABASE:-tractorspecs}'
      POSTGRES_USER: '${DB_USERNAME:-tractorspecs}'
      POSTGRES_PASSWORD: '${DB_PASSWORD:-secret}'
    volumes:
      - 'sail-pgsql:/var/lib/postgresql/data'
    networks:
      - sail

  redis:
    image: 'redis:alpine'
    ports:
      - '${FORWARD_REDIS_PORT:-6379}:6379'
    networks:
      - sail

  minio:
    image: 'minio/minio:latest'
    ports:
      - '${FORWARD_MINIO_PORT:-9000}:9000'
      - '${FORWARD_MINIO_CONSOLE_PORT:-8900}:8900'
    environment:
      MINIO_ROOT_USER: '${MINIO_ROOT_USER:-sail}'
      MINIO_ROOT_PASSWORD: '${MINIO_ROOT_PASSWORD:-password}'
    volumes:
      - 'sail-minio:/data/minio'
    command: minio server /data/minio --console-address ":8900"
    networks:
      - sail
```

---

### Step 20 — Production Checklist

```bash
# Cache config, routes, views
vendor/bin/sail artisan config:cache
vendor/bin/sail artisan route:cache
vendor/bin/sail artisan view:cache
vendor/bin/sail artisan optimize

# Generate sitemap post-deploy
vendor/bin/sail artisan app:generate-sitemap

# Run pending migrations
vendor/bin/sail artisan migrate --force

# Format PHP
vendor/bin/duster fix --dirty
```

Set in production `.env`:
```
APP_ENV=production
APP_DEBUG=false
LOG_LEVEL=error
```

PostgreSQL tuning (for 500k+ models):
- `shared_buffers = 256MB`
- `work_mem = 16MB`
- `effective_cache_size = 1GB`
- `random_page_cost = 1.1` (SSD)

Redis:
- `maxmemory-policy allkeys-lru`
- `maxmemory 512mb`

---

## Implementation Order

| Phase | # | Task |
|-------|---|------|
| 1 | 1 | Bootstrap project, install packages, configure .env |
| 1 | 2 | pg_trgm extension migration |
| 1 | 3 | All database migrations (in order) |
| 1 | 4 | Eloquent models with relationships, scopes, casts |
| 1 | 5 | Factories + DatabaseSeeder |
| 2 | 6 | Route definitions (public + admin) |
| 2 | 7 | All public controllers |
| 2 | 8 | RelatedModelsService, SearchService, CacheService |
| 2 | 9 | Model observers (cache invalidation) |
| 3 | 10 | Blade layouts (app + admin) |
| 3 | 11 | Blade components (breadcrumb, spec-table, model-card, etc.) |
| 3 | 12 | All public views |
| 3 | 13 | SEO meta, Schema.org JSON-LD, sitemap command |
| 4 | 14 | Fortify auth + login view |
| 4 | 15 | Livewire admin components |
| 5 | 16 | Redis cache configuration |
| 5 | 17 | Query optimization audit (N+1 check) |
| 6 | 18 | Pest feature tests for all public pages + admin |
| 7 | 19 | docker-compose.yml finalization |
| 7 | 20 | Production checklist + deployment scripts |
