<div align="center">

# FurnaceOps

**Read-only asset observability for furnace maintenance operations**

<sub>component status · measurement quality · work-record traceability · synthetic demonstration data</sub>

</div>

FurnaceOps is a local software prototype for reviewing component status and tracing work records in an industrial furnace maintenance workflow. The current release focuses on suspended platforms and protective shelters, combining an interactive layout, time-series measurements, status-quality checks, and searchable operation records in one read-only interface.

The repository contains a deterministic demonstration built entirely with the Python standard library, SQLite, HTML, CSS, and JavaScript. It uses synthetic data, runs locally, and does not connect to enterprise systems or issue equipment-control commands.

## Functions

- Interactive component layout with group and text filters
- Explicit valid, stale, missing, and invalid measurement states
- Per-component measurement history with preserved data gaps
- Work-record queries by component and operating stage
- CSV export that follows the active record filters
- Read-only HTTP API with local SQLite storage

## Run locally

Python 3.10 or later is required. No third-party package is needed.

```bash
python app.py
```

Open `http://127.0.0.1:8767` in a browser. A new local database is initialized on first use from the fixed synthetic dataset.

Run the test suite with:

```bash
python -m unittest discover -s tests -v
```

## API

| Endpoint | Purpose |
|:---|:---|
| `GET /api/health` | Service status and operating mode |
| `GET /api/summary` | Asset, record, and measurement-quality summary |
| `GET /api/assets` | Filterable component inventory |
| `GET /api/assets/{id}` | Component detail |
| `GET /api/assets/{id}/series` | Measurement history |
| `GET /api/records` | Paginated work records |
| `GET /api/records.csv` | Filtered CSV export |

All write methods are disabled.

## Repository structure

```text
FurnaceOps/
├── app.py              # local HTTP API, SQLite schema, and synthetic fixtures
├── static/             # browser interface
├── tests/              # API, data-quality, export, and security tests
├── backend/            # reserved application-service structure
├── frontend/           # reserved modular frontend structure
├── config/             # reserved configuration layer
└── deploy/             # reserved deployment layer
```

## Scope

This repository is a software demonstrator. Its layout, measurements, and work records are synthetic and must not be used for engineering assessment, safety decisions, or operational control. Enterprise authentication, field-data adapters, permissions, and production deployment are outside the current release.

