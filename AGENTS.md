<laravel-boost-guidelines>
=== foundation rules ===

# Laravel Boost Guidelines

The Laravel Boost guidelines are specifically curated by Laravel maintainers for this application. These guidelines should be followed closely to ensure the best experience when building Laravel applications.

## Foundational Context

This application is a Laravel application and its main Laravel ecosystems package & versions are below. You are an expert with them all. Ensure you abide by these specific packages & versions.

- php - 8.5.3
- laravel/fortify (FORTIFY) - v1
- laravel/framework (LARAVEL) - v12
- laravel/prompts (PROMPTS) - v0
- livewire/flux (FLUXUI_FREE) - v2
- livewire/flux-pro (FLUXUI_PRO) - v
- livewire/livewire (LIVEWIRE) - v4
- larastan/larastan (LARASTAN) - v3
- laravel/boost (BOOST) - v2
- laravel/mcp (MCP) - v0
- laravel/pail (PAIL) - v1
- laravel/pint (PINT) - v1
- laravel/sail (SAIL) - v1
- pestphp/pest (PEST) - v4
- phpunit/phpunit (PHPUNIT) - v12
- rector/rector (RECTOR) - v2
- tailwindcss (TAILWINDCSS) - v4

## Skills Activation

This project has domain-specific skills available. You MUST activate the relevant skill whenever you work in that domain—don't wait until you're stuck.

- `fluxui-development` — Develops UIs with Flux UI Pro components. Activates when creating buttons, forms, modals, inputs, tables, charts, date pickers, or UI components; replacing HTML elements with Flux; working with flux: components; or when the user mentions Flux, component library, UI components, form fields, or asks about available Flux components.
- `livewire-development` — Develops reactive Livewire 4 components. Activates when creating, updating, or modifying Livewire components; working with wire:model, wire:click, wire:loading, or any wire: directives; adding real-time updates, loading states, or reactivity; debugging component behavior; writing Livewire tests; or when the user mentions Livewire, component, counter, or reactive UI.
- `pest-testing` — Tests applications using the Pest 4 PHP framework. Activates when writing tests, creating unit or feature tests, adding assertions, testing Livewire components, browser testing, debugging test failures, working with datasets or mocking; or when the user mentions test, spec, TDD, expects, assertion, coverage, or needs to verify functionality works.
- `tailwindcss-development` — Styles applications using Tailwind CSS v4 utilities. Activates when adding styles, restyling components, working with gradients, spacing, layout, flex, grid, responsive design, dark mode, colors, typography, or borders; or when the user mentions CSS, styling, classes, Tailwind, restyle, hero section, cards, buttons, or any visual/UI changes.
- `developing-with-fortify` — Laravel Fortify headless authentication backend development. Activate when implementing authentication features including login, registration, password reset, email verification, two-factor authentication (2FA/TOTP), profile updates, headless auth, authentication scaffolding, or auth guards in Laravel applications.
- `laravel-pdf` — Generate PDFs from Blade views or HTML using spatie/laravel-pdf. Covers creating, formatting, saving, downloading, and testing PDFs with the Browsershot, Cloudflare, or DOMPDF driver.
- `api-design-patterns` — RESTful API design, error handling, versioning, and best practices. Use when designing APIs, reviewing endpoints, implementing error responses, or setting up API structure. Triggers on &quot;design API&quot;, &quot;review API&quot;, &quot;REST best practices&quot;, or &quot;API patterns&quot;.
- `api-resource-patterns` — Best practices for Laravel API Resources including resource transformation, collection handling, conditional attributes, and relationship loading.
- `laravel:api-resources-and-pagination` — Use API Resources with pagination and conditional fields; keep response shapes stable and cache-friendly
- `brainstorming-laravel` — Use when creating or developing Laravel features, before writing code or implementation plans - refines rough ideas into fully-formed Laravel designs through collaborative questioning, alternative exploration, and incremental validation.
- `clean-code-principles` — SOLID principles, design patterns, DRY, KISS, and clean code fundamentals. Use when reviewing architecture, checking code quality, refactoring, or discussing design decisions. Triggers on &quot;review architecture&quot;, &quot;check code quality&quot;, &quot;SOLID principles&quot;, &quot;design patterns&quot;, or &quot;clean code&quot;.
- `eloquent-best-practices` — Best practices for Laravel Eloquent ORM including query optimization, relationship management, and avoiding common pitfalls like N+1 queries.
- `git-workflow` — Git best practices, branching strategies, commit conventions, and PR workflows. Use when reviewing git history, writing commits, setting up branching strategy, or improving git practices. Triggers on &quot;git best practices&quot;, &quot;commit message&quot;, &quot;branching strategy&quot;, or &quot;PR workflow&quot;.
- `laravel-best-practices` — Laravel 12 conventions and best practices. Use when creating controllers, models, migrations, validation, services, or structuring Laravel applications. Triggers on tasks involving Laravel architecture, Eloquent, database, API development, or PHP patterns.
- `laravel-specialist` — Use when building Laravel 10+ applications requiring Eloquent ORM, API resources, or queue systems. Invoke for Laravel models, Livewire components, Sanctum authentication, Horizon queues.
- `laravel-tdd` — Test-Driven Development specifically for Laravel applications using Pest PHP. Use when implementing any Laravel feature or bugfix - write the test first, watch it fail, write minimal code to pass.
- `php-best-practices` — PHP 8.5+ modern patterns, PSR standards, and SOLID principles. Use when reviewing PHP code, checking type safety, auditing code quality, or ensuring PHP best practices. Triggers on &quot;review PHP&quot;, &quot;check PHP code&quot;, &quot;audit PHP&quot;, or &quot;PHP best practices&quot;.
- `php-pro` — Use when building PHP applications with modern PHP 8.3+ features, Laravel, or Symfony frameworks. Invoke for strict typing, PHPStan level 9, async patterns with Swoole, PSR standards.
- `postgres-pro` — Use when optimizing PostgreSQL queries, configuring replication, or implementing advanced database features. Invoke for EXPLAIN analysis, JSONB operations, extension usage, VACUUM tuning, performance monitoring.
- `sql-pro` — Use when optimizing SQL queries, designing database schemas, or tuning database performance. Invoke for complex queries, window functions, CTEs, indexing strategies, query plan analysis.
- `systematic-debugging-laravel` — Systematic debugging process for Laravel applications - ensures root cause investigation before attempting fixes. Use for any Laravel issue (test failures, bugs, unexpected behavior, performance problems).
- `tailwind-best-practices` — Tailwind CSS patterns and conventions. Use when writing responsive designs, implementing dark mode, creating reusable component styles, or configuring Tailwind. Triggers on tasks involving Tailwind classes, responsive design, dark mode, or CSS styling.
- `testing-best-practices` — Unit testing, integration testing, and test-driven development principles. Use when writing tests, reviewing test code, improving test coverage, or setting up testing strategy. Triggers on &quot;write tests&quot;, &quot;review tests&quot;, &quot;testing best practices&quot;, or &quot;TDD&quot;.
- `web-design-guidelines` — Review UI code for Web Interface Guidelines compliance. Use when asked to &quot;review my UI&quot;, &quot;check accessibility&quot;, &quot;audit design&quot;, &quot;review UX&quot;, or &quot;check my site against best practices&quot;.

## Conventions

- You must follow all existing code conventions used in this application. When creating or editing a file, check sibling files for the correct structure, approach, and naming.
- Use descriptive names for variables and methods. For example, `isRegisteredForDiscounts`, not `discount()`.
- Check for existing components to reuse before writing a new one.

## Verification Scripts

- Do not create verification scripts or tinker when tests cover that functionality and prove they work. Unit and feature tests are more important.

## Application Structure & Architecture

- Stick to existing directory structure; don't create new base folders without approval.
- Do not change the application's dependencies without approval.

## Frontend Bundling

- If the user doesn't see a frontend change reflected in the UI, it could mean they need to run `vendor/bin/sail npm run build`, `vendor/bin/sail npm run dev`, or `vendor/bin/sail composer run dev`. Ask them.

## Documentation Files

- You must only create documentation files if explicitly requested by the user.

## Replies

- Be concise in your explanations - focus on what's important rather than explaining obvious details.

=== boost rules ===

# Laravel Boost

- Laravel Boost is an MCP server that comes with powerful tools designed specifically for this application. Use them.

## Artisan

- Use the `list-artisan-commands` tool when you need to call an Artisan command to double-check the available parameters.

## URLs

- Whenever you share a project URL with the user, you should use the `get-absolute-url` tool to ensure you're using the correct scheme, domain/IP, and port.

## Tinker / Debugging

- You should use the `tinker` tool when you need to execute PHP to debug code or query Eloquent models directly.
- Use the `database-query` tool when you only need to read from the database.
- Use the `database-schema` tool to inspect table structure before writing migrations or models.

## Reading Browser Logs With the `browser-logs` Tool

- You can read browser logs, errors, and exceptions using the `browser-logs` tool from Boost.
- Only recent browser logs will be useful - ignore old logs.

## Searching Documentation (Critically Important)

- Boost comes with a powerful `search-docs` tool you should use before trying other approaches when working with Laravel or Laravel ecosystem packages. This tool automatically passes a list of installed packages and their versions to the remote Boost API, so it returns only version-specific documentation for the user's circumstance. You should pass an array of packages to filter on if you know you need docs for particular packages.
- Search the documentation before making code changes to ensure we are taking the correct approach.
- Use multiple, broad, simple, topic-based queries at once. For example: `['rate limiting', 'routing rate limiting', 'routing']`. The most relevant results will be returned first.
- Do not add package names to queries; package information is already shared. For example, use `test resource table`, not `filament 4 test resource table`.

### Available Search Syntax

1. Simple Word Searches with auto-stemming - query=authentication - finds 'authenticate' and 'auth'.
2. Multiple Words (AND Logic) - query=rate limit - finds knowledge containing both "rate" AND "limit".
3. Quoted Phrases (Exact Position) - query="infinite scroll" - words must be adjacent and in that order.
4. Mixed Queries - query=middleware "rate limit" - "middleware" AND exact phrase "rate limit".
5. Multiple Queries - queries=["authentication", "middleware"] - ANY of these terms.

=== php rules ===

# PHP

- Always use curly braces for control structures, even for single-line bodies.

## Constructors

- Use PHP 8 constructor property promotion in `__construct()`.
    - `public function __construct(public GitHub $github) { }`
- Do not allow empty `__construct()` methods with zero parameters unless the constructor is private.

## Type Declarations

- Always use explicit return type declarations for methods and functions.
- Use appropriate PHP type hints for method parameters.

<!-- Explicit Return Types and Method Params -->
```php
protected function isAccessible(User $user, ?string $path = null): bool
{
    ...
}
```

## Enums

- Typically, keys in an Enum should be TitleCase. For example: `FavoritePerson`, `BestLake`, `Monthly`.

## Comments

- Prefer PHPDoc blocks over inline comments. Never use comments within the code itself unless the logic is exceptionally complex.

## PHPDoc Blocks

- Add useful array shape type definitions when appropriate.

=== sail rules ===

# Laravel Sail

- This project runs inside Laravel Sail's Docker containers. You MUST execute all commands through Sail.
- Start services using `vendor/bin/sail up -d` and stop them with `vendor/bin/sail stop`.
- Open the application in the browser by running `vendor/bin/sail open`.
- Always prefix PHP, Artisan, Composer, and Node commands with `vendor/bin/sail`. Examples:
    - Run Artisan Commands: `vendor/bin/sail artisan migrate`
    - Install Composer packages: `vendor/bin/sail composer install`
    - Execute Node commands: `vendor/bin/sail npm run dev`
    - Execute PHP scripts: `vendor/bin/sail php [script]`
- View all available Sail commands by running `vendor/bin/sail` without arguments.

=== tests rules ===

# Test Enforcement

- Every change must be programmatically tested. Write a new test or update an existing test, then run the affected tests to make sure they pass.
- Run the minimum number of tests needed to ensure code quality and speed. Use `vendor/bin/sail artisan test --compact` with a specific filename or filter.

=== laravel/core rules ===

# Do Things the Laravel Way

- Use `vendor/bin/sail artisan make:` commands to create new files (i.e. migrations, controllers, models, etc.). You can list available Artisan commands using the `list-artisan-commands` tool.
- If you're creating a generic PHP class, use `vendor/bin/sail artisan make:class`.
- Pass `--no-interaction` to all Artisan commands to ensure they work without user input. You should also pass the correct `--options` to ensure correct behavior.

## Database

- Always use proper Eloquent relationship methods with return type hints. Prefer relationship methods over raw queries or manual joins.
- Use Eloquent models and relationships before suggesting raw database queries.
- Avoid `DB::`; prefer `Model::query()`. Generate code that leverages Laravel's ORM capabilities rather than bypassing them.
- Generate code that prevents N+1 query problems by using eager loading.
- Use Laravel's query builder for very complex database operations.

### Model Creation

- When creating new models, create useful factories and seeders for them too. Ask the user if they need any other things, using `list-artisan-commands` to check the available options to `vendor/bin/sail artisan make:model`.

### APIs & Eloquent Resources

- For APIs, default to using Eloquent API Resources and API versioning unless existing API routes do not, then you should follow existing application convention.

## Controllers & Validation

- Always create Form Request classes for validation rather than inline validation in controllers. Include both validation rules and custom error messages.
- Check sibling Form Requests to see if the application uses array or string based validation rules.

## Authentication & Authorization

- Use Laravel's built-in authentication and authorization features (gates, policies, Sanctum, etc.).

## URL Generation

- When generating links to other pages, prefer named routes and the `route()` function.

## Queues

- Use queued jobs for time-consuming operations with the `ShouldQueue` interface.

## Configuration

- Use environment variables only in configuration files - never use the `env()` function directly outside of config files. Always use `config('app.name')`, not `env('APP_NAME')`.

## Testing

- When creating models for tests, use the factories for the models. Check if the factory has custom states that can be used before manually setting up the model.
- Faker: Use methods such as `$this->faker->word()` or `fake()->randomDigit()`. Follow existing conventions whether to use `$this->faker` or `fake()`.
- When creating tests, make use of `vendor/bin/sail artisan make:test [options] {name}` to create a feature test, and pass `--unit` to create a unit test. Most tests should be feature tests.

## Vite Error

- If you receive an "Illuminate\Foundation\ViteException: Unable to locate file in Vite manifest" error, you can run `vendor/bin/sail npm run build` or ask the user to run `vendor/bin/sail npm run dev` or `vendor/bin/sail composer run dev`.

=== laravel/v12 rules ===

# Laravel 12

- CRITICAL: ALWAYS use `search-docs` tool for version-specific Laravel documentation and updated code examples.
- Since Laravel 11, Laravel has a new streamlined file structure which this project uses.

## Laravel 12 Structure

- In Laravel 12, middleware are no longer registered in `app/Http/Kernel.php`.
- Middleware are configured declaratively in `bootstrap/app.php` using `Application::configure()->withMiddleware()`.
- `bootstrap/app.php` is the file to register middleware, exceptions, and routing files.
- `bootstrap/providers.php` contains application specific service providers.
- The `app\Console\Kernel.php` file no longer exists; use `bootstrap/app.php` or `routes/console.php` for console configuration.
- Console commands in `app/Console/Commands/` are automatically available and do not require manual registration.

## Database

- When modifying a column, the migration must include all of the attributes that were previously defined on the column. Otherwise, they will be dropped and lost.
- Laravel 12 allows limiting eagerly loaded records natively, without external packages: `$query->latest()->limit(10);`.

### Models

- Casts can and likely should be set in a `casts()` method on a model rather than the `$casts` property. Follow existing conventions from other models.

=== fluxui-pro/core rules ===

# Flux UI Pro

- Flux UI is the official Livewire component library. This project uses the Pro edition, which includes all free and Pro components and variants.
- Use `<flux:*>` components when available; they are the recommended way to build Livewire interfaces.
- IMPORTANT: Activate `fluxui-development` when working with Flux UI components.

=== fluxui-pro/v rules ===

# Flux UI Pro

- Flux UI is the official Livewire component library. This project uses the Pro edition, which includes all free and Pro components and variants.
- Use `<flux:*>` components when available; they are the recommended way to build Livewire interfaces.
- IMPORTANT: Activate `fluxui-development` when working with Flux UI components.

=== livewire/core rules ===

# Livewire

- Livewire allows you to build dynamic, reactive interfaces using only PHP — no JavaScript required.
- Instead of writing frontend code in JavaScript frameworks, you use Alpine.js to build the UI when client-side interactions are required.
- State lives on the server; the UI reflects it. Validate and authorize in actions (they're like HTTP requests).
- IMPORTANT: Activate `livewire-development` every time you're working with Livewire-related tasks.

=== pint/core rules ===

# Laravel Pint Code Formatter

- If you have modified any PHP files, you must run `vendor/bin/sail bin pint --dirty --format agent` before finalizing changes to ensure your code matches the project's expected style.
- Do not run `vendor/bin/sail bin pint --test --format agent`, simply run `vendor/bin/sail bin pint --format agent` to fix any formatting issues.

=== pest/core rules ===

## Pest

- This project uses Pest for testing. Create tests: `vendor/bin/sail artisan make:test --pest {name}`.
- Run tests: `vendor/bin/sail artisan test --compact` or filter: `vendor/bin/sail artisan test --compact --filter=testName`.
- Do NOT delete tests without approval.
- CRITICAL: ALWAYS use `search-docs` tool for version-specific Pest documentation and updated code examples.
- IMPORTANT: Activate `pest-testing` every time you're working with a Pest or testing-related task.

=== tailwindcss/core rules ===

# Tailwind CSS

- Always use existing Tailwind conventions; check project patterns before adding new ones.
- IMPORTANT: Always use `search-docs` tool for version-specific Tailwind CSS documentation and updated code examples. Never rely on training data.
- IMPORTANT: Activate `tailwindcss-development` every time you're working with a Tailwind CSS or styling-related task.

=== laravel/fortify rules ===

# Laravel Fortify

- Fortify is a headless authentication backend that provides authentication routes and controllers for Laravel applications.
- IMPORTANT: Always use the `search-docs` tool for detailed Laravel Fortify patterns and documentation.
- IMPORTANT: Activate `developing-with-fortify` skill when working with Fortify authentication features.

=== revolution/laravel-boost-phpstorm-copilot rules ===

## PhpStorm with GitHub Copilot Plugin

This package provides custom CodeEnvironment integration for PhpStorm with GitHub Copilot plugin with Laravel Boost. It enables PhpStorm users to leverage Laravel Boost's MCP (Model Context Protocol) server functionality.

### Important: Project Path Verification

**Before using Laravel Boost MCP tools in PhpStorm with GitHub Copilot plugin, verify that the project path in the global MCP configuration file matches your current project.**

The MCP configuration file is stored system-wide at:
- macOS, Linux: `~/.config/github-copilot/intellij/mcp.json`
- Windows: `%LOCALAPPDATA%\github-copilot\intellij\mcp.json`

If the project path in the MCP configuration does not match your current Laravel project, **you must update it before using MCP tools**:

<code-snippet name="Update MCP Configuration for Current Project" lang="bash">
php artisan boost:install --guidelines --skills --mcp --no-interaction
</code-snippet>

This command updates the MCP configuration file with the absolute path to your current Laravel project, ensuring MCP tools interact with the correct project.

### When to Run boost:install

Run `php artisan boost:install` whenever you:
- Switch to a different Laravel project
- Clone or move your project to a new location
- Notice MCP tools are accessing the wrong project's data

### Why This is Necessary

Unlike project-local MCP configurations, PhpStorm with GitHub Copilot plugin stores MCP server configurations in a system-wide location. This allows multiple projects to share the same MCP server registration, but requires updating the configuration when switching between projects to ensure the correct project path is used.

=== tightenco/duster rules ===

## Duster Code Formatter

- You must run `vendor/bin/duster fix --dirty` before finalizing changes to ensure your code matches the project's expected style.
- Duster wraps Laravel Pint and other formatters, so never run Pint directly. Always prefer Duster for formatting tasks.

</laravel-boost-guidelines>
