# Adaptive Admin Panel

A flexible, API-first admin panel built with FastAPI and SQLAlchemy ORM. Connects to any database supported by SQLAlchemy — swap databases by changing a single connection string.

## Features

- **API-First Architecture**: All data operations go through REST API endpoints
- **Database Agnostic**: Connect to SQLite, MySQL, PostgreSQL, or other SQLAlchemy-supported databases
- **Soft Delete**: All records use `deleted_at`/`deleted_by` columns instead of hard deletes
- **Modern UI**: Built with Tabler CSS framework for a clean, responsive interface
- **Dynamic Schema Viewer**: Inspect database tables, columns, and sample data

## Supported Databases

| Backend    | `DATABASE_URL` format                                  | Extra install            |
|------------|--------------------------------------------------------|--------------------------|
| SQLite     | `sqlite:///./admin.db`                                 | None (built-in)          |
| MySQL      | `mysql+pymysql://user:pass@host:3306/db`               | `uv pip install pymysql` |
| PostgreSQL | `postgresql://user:pass@host:5432/db`                  | `uv pip install psycopg2-binary` |

## Quick Start

```bash
uv sync
cp .env.example .env
uv run python local_db_setup.py
uv run uvicorn app.main:app --reload
```

Open http://localhost:8000 to access the admin panel.

## Database Setup

For local SQLite development, initialize tables from the SQLAlchemy models:

```bash
uv run python local_db_setup.py
```

For existing or non-SQLite databases, set up your schema externally using the SQL definitions below, then connect via `DATABASE_URL` in your `.env` file.

### Schema Definition

```sql
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

-- Indexes
CREATE INDEX idx_customer_notes_customer_id ON customer_notes(customer_id);
CREATE INDEX idx_customer_config_matrix_customer_id ON customer_config_matrix(customer_id);
CREATE INDEX idx_customer_config_matrix_preset_config_id ON customer_config_matrix(preset_config_id);
CREATE INDEX idx_customer_config_matrix_custom_config_id ON customer_config_matrix(custom_config_id);
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
| `/db-schema` | Database schema viewer |

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
| `DATABASE_URL` | `sqlite:///./admin.db` | Database connection string |
| `DEBUG` | `false` | Enable debug mode |
| `SECRET_KEY` | `changeme` | Secret key for sessions |
| `PRIMARY_COLOR` | `#0054a6` | UI primary color |
| `BRAND_NAME` | `Admin Panel` | Application name |

## Installing Database Drivers

```bash
uv sync --extra mysql      # MySQL
uv sync --extra postgres   # PostgreSQL
```

Then update `DATABASE_URL` in `.env` to point to your database.
