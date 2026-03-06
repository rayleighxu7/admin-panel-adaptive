# Adaptive Admin Panel

Adaptive Admin Panel is a FastAPI + SQLAlchemy application for managing customers, notes, preset configs, and customer-config assignments through a web UI and REST APIs.

## Highlights

- API-first architecture with page routes powered by the same backend models
- Session-based admin authentication
- Soft-delete support for business entities (`deleted_at` / `deleted_by`)
- Audit logging for all mutating requests (`POST`, `PUT`, `PATCH`, `DELETE`)
- Database schema explorer (`/schema`) with resizable table columns
- Bulk actions for admin workflows
- Customer activity timeline (notes + assignments + audit excerpts)
- Brand theming via environment-driven color variables

## Supported Databases

| Backend    | `DATABASE_URL` format                    | Extra install                 |
|------------|------------------------------------------|-------------------------------|
| SQLite     | `sqlite:///./sqlite.db`                  | None                          |
| MySQL      | `mysql+pymysql://user:pass@host:3306/db`| `uv sync --extra mysql`       |
| PostgreSQL | `postgresql://user:pass@host:5432/db`   | `uv sync --extra postgres`    |

## Quick Start

```bash
uv sync
cp .env.example .env
uv run python scripts/local_db_setup.py
uv run python scripts/create_admin_user.py --username admin
uv run uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

## Authentication and Access Control

- All non-static routes require authentication when `ENABLE_AUTH=true`.
- Sessions are stored in signed cookies using `SECRET_KEY`.
- `admin` user has exclusive access to Reference resources:
  - `/schema`
  - `/api/schema`
  - `/docs`
  - `/openapi.json`
  - `/redoc`
- Non-admin users are redirected (or receive `403` for API-style requests).

## Audit Logging

Every mutating request (`POST`, `PUT`, `PATCH`, `DELETE`) is written to `audit_log` by middleware.

Captured fields include:

- UTC event timestamp
- HTTP method and endpoint
- query parameters and path parameters
- request body (with basic sensitive-field redaction)
- response status code
- authenticated admin user metadata
- client IP and user agent
- runtime error text if the request raises

## Database Setup

### Initialize schema from models

```bash
uv run python scripts/local_db_setup.py
```

### Core schema (reference SQL)

```sql
-- Admin users (for login)
CREATE TABLE admin_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Customers table
CREATE TABLE customers (
    id VARCHAR(36) PRIMARY KEY NOT NULL,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(30),
    address TEXT,
    date_of_birth DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    deleted_at DATETIME,
    deleted_by VARCHAR(100)
);

-- Customer notes
CREATE TABLE customer_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    customer_id VARCHAR(36) NOT NULL REFERENCES customers(id),
    note TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    deleted_at DATETIME,
    deleted_by VARCHAR(100)
);

-- Preset configurations
CREATE TABLE preset_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    name VARCHAR(100) NOT NULL UNIQUE,
    config JSON NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    deleted_at DATETIME,
    deleted_by VARCHAR(100)
);

-- Custom configurations
CREATE TABLE custom_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    config JSON NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    deleted_at DATETIME,
    deleted_by VARCHAR(100)
);

-- Customer config assignments (links customer to preset OR custom config)
CREATE TABLE customer_config_matrix (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    customer_id VARCHAR(36) NOT NULL REFERENCES customers(id),
    preset_config_id INTEGER REFERENCES preset_configs(id),
    custom_config_id INTEGER REFERENCES custom_configs(id),
    effective_from DATE NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    deleted_at DATETIME,
    deleted_by VARCHAR(100),
    CHECK ((preset_config_id IS NULL) != (custom_config_id IS NULL))
);

-- Audit log for mutating endpoints
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    event_time_utc DATETIME NOT NULL,
    method VARCHAR(10) NOT NULL,
    endpoint VARCHAR(500) NOT NULL,
    query_params JSON NOT NULL,
    path_params JSON NOT NULL,
    request_body JSON NOT NULL,
    response_status_code INTEGER NOT NULL,
    admin_user_id INTEGER,
    admin_username VARCHAR(100),
    client_ip VARCHAR(64),
    user_agent VARCHAR(512),
    error VARCHAR(1000)
);

-- Indexes
CREATE INDEX idx_customer_notes_customer_id ON customer_notes(customer_id);
CREATE INDEX idx_customer_config_matrix_customer_id ON customer_config_matrix(customer_id);
CREATE INDEX idx_customer_config_matrix_preset_config_id ON customer_config_matrix(preset_config_id);
CREATE INDEX idx_customer_config_matrix_custom_config_id ON customer_config_matrix(custom_config_id);
CREATE INDEX idx_audit_log_event_time_utc ON audit_log(event_time_utc);
CREATE INDEX idx_audit_log_endpoint ON audit_log(endpoint);
```

### Config JSON Structure

The `config` field in `preset_configs` and `custom_configs` uses this structure:

```json
{
  "commission_percentage": 0.025,
  "affiliate_percentage": 0.01,
  "gmv_percentage": 0.005,
  "per_order": {
    "fee_cents": 150,
    "quantity_threshold": 10
  },
  "flat_fee_cents": 500
}
```

**Note**: Percentage values are stored as decimals between 0 and 1 (e.g., 2.5% = 0.025).

## API Endpoints

### Customers

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/customers` | List customers (supports `search`, `limit`, `offset`) |
| GET | `/api/customers/{id}` | Get customer by ID |
| POST | `/api/customers` | Create customer |
| PATCH | `/api/customers/{id}` | Update customer |
| DELETE | `/api/customers/{id}` | Soft delete customer |

### Customer Notes

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/customers/{id}/notes` | List notes for customer |
| POST | `/api/customers/{id}/notes` | Create note |
| PATCH | `/api/customers/{id}/notes/{note_id}` | Update note |
| DELETE | `/api/customers/{id}/notes/{note_id}` | Soft delete note |

### Preset Configs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/preset-configs` | List preset configs (supports `search`, `limit`, `offset`) |
| GET | `/api/preset-configs/{id}` | Get preset config by ID |
| POST | `/api/preset-configs` | Create preset config |
| PATCH | `/api/preset-configs/{id}` | Update preset config |
| DELETE | `/api/preset-configs/{id}` | Soft delete (fails if linked to customers) |

### Config Matrix

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/config-matrix` | List assignments (supports `customer_id`, `limit`, `offset`) |
| GET | `/api/config-matrix/{id}` | Get assignment by ID |
| POST | `/api/config-matrix` | Create assignment (preset OR inline custom config) |
| PATCH | `/api/config-matrix/{id}` | Update assignment |
| DELETE | `/api/config-matrix/{id}` | Soft delete assignment |

### Schema Introspection

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/schema` | Get all tables with columns and sample data |

## Frontend Pages

| Path | Description |
|------|-------------|
| `/customers` | Customer list with search, pagination, and CRUD drawer |
| `/customers/{id}` | Customer detail with notes and config assignments |
| `/preset-configs` | Preset config list with CRUD drawer |
| `/preset-configs/{id}` | Preset detail with linked customers |
| `/config-matrix` | Config assignments with customer filter |
| `/schema` | Database schema viewer (admin only) |
| `/login` | Login page |
| `/logout` | Ends session and redirects to login |

## Project Structure

```
app/
├── main.py              # FastAPI app, lifespan, router setup
├── config.py            # Pydantic Settings (env-driven config)
├── database.py          # SQLAlchemy engine lifecycle
├── models.py            # ORM models (Customer, PresetConfig, etc.)
├── branding/
│   └── router.py        # Dynamic brand CSS endpoint
├── customers/
│   └── router.py        # Customer API + page routes
├── customer_notes/
│   └── router.py        # Customer notes API
├── preset_configs/
│   └── router.py        # Preset config API + page routes
├── config_matrix/
│   └── router.py        # Config matrix API + page routes
└── db_schema/
    └── router.py        # Schema introspection API + page

templates/
├── layout.html          # Base template with sidebar
├── customers.html       # Customer list page
├── customer_detail.html # Customer detail page
├── preset_configs.html  # Preset config list page
├── preset_config_detail.html
├── config_matrix.html   # Config assignments page
└── dev_database.html    # Schema viewer page

statics/
└── custom.css           # Custom styles
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./sqlite.db` | Database connection string |
| `DEBUG` | `false` | Enable debug mode |
| `ENABLE_AUTH` | `true` | Require login/session auth for all pages/APIs (except static assets and login routes) |
| `SECRET_KEY` | `change-me-in-production` | Secret used to sign session cookies (must be overridden in production) |
| `SESSION_COOKIE_NAME` | `admin_panel_session` | Session cookie name |
| `SESSION_MAX_AGE_SECONDS` | `28800` | Session lifetime in seconds |
| `SESSION_HTTPS_ONLY` | `true` | Mark session cookie as HTTPS-only |
| `ENABLE_SCHEMA_BROWSER` | `true` | Enable DB schema explorer routes (`/schema`, `/api/schema`) |
| `ENABLE_SCHEMA_SAMPLE_ROWS` | `true` | Include sample row data in schema API responses |
| `SCHEMA_SAMPLE_LIMIT` | `10` | Max sample rows per table when enabled |
| `SCHEMA_INCLUDE_ROW_COUNTS` | `true` | Include per-table row counts in `/api/schema` responses |
| `SCHEMA_EXPORT_MAX_ROWS` | `5000` | Hard cap for `/api/schema/export.csv` row exports |
| `BRAND_PRIMARY` | `#206bc4` | UI primary color |
| `BRAND_SIDEBAR_BG` | `#1b2434` | Sidebar background color |
| `BRAND_SIDEBAR_TEXT` | `#ffffff` | Sidebar text color |
| `BRAND_LOGO_URL` | `/images/freelanxur-logo-transparent.PNG` | Sidebar logo image URL/path |

Create or rotate an admin user manually:

```bash
uv run python scripts/create_admin_user.py --username admin
```

## Installing Database Drivers

```bash
uv sync --extra mysql      # MySQL
uv sync --extra postgres   # PostgreSQL
```

Then update `DATABASE_URL` in `.env` to point to your database.
