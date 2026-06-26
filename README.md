# DataFlow CI

A distributed CI system for data pipelines. It watches a Git repository for new commits, validates pipeline output files against declared expectations, and surfaces results in a real-time dashboard.

## How it works

```
Observer → detects new commit → Dispatcher → assigns job → Runner(s) → submit results
                                                                ↑
                                                          Dashboard polls
```

| Service | Role |
|---|---|
| **Dispatcher** | FastAPI job queue (SQLite). Manages job lifecycle, runner registration, heartbeat monitoring, and job reassignment on runner failure. |
| **Observer** | Polls a Git repo for new commits. Dispatches a validation job for each new HEAD. |
| **Runner** | Pulls assigned jobs, runs all three check categories, posts results back. Scales horizontally — two run by default. |
| **Dashboard** | React SPA. Polls the dispatcher every 5s. Shows job status and per-check results. |

## Quick start

```bash
docker compose up --build
```

- Dispatcher API: http://localhost:8000
- Dashboard: run separately (see below)

**Dashboard dev server:**
```bash
cd dashboard
npm install
npm run dev    # http://localhost:5173
```

**Run checks locally without Docker:**
```bash
cd runner
pip install -r requirements.txt
python smoke_test.py    # runs against tests/sample_pipeline
```

## Defining expectations

Place a `dataflow_expectations.yml` at the root of the watched repository. The runner validates all CSV/Parquet files in the `outputs/` directory against it.

```yaml
orders.csv:
  min_rows: 100
  primary_key:
    - order_id
  columns:
    order_id:
      dtype: int
      nullable: false
    status:
      dtype: object
      allowed_values: [pending, shipped, delivered, cancelled]
    quantity:
      dtype: int
      min_value: 1
      check_outliers: true
      max_outlier_ratio: 0.05

relationships:
  - source_file: orders.csv
    source_column: product_id
    target_file: products.csv
    target_column: product_id

join_coverage:
  - left_file: orders.csv
    left_column: product_id
    right_file: products.csv
    right_column: product_id
    min_coverage_ratio: 0.98

freshness:
  - file: orders.csv
    max_age_hours: 48
```

**Check categories:**

- **Structural** — column existence, dtypes, nullability, primary key uniqueness, row count bounds
- **Statistical** — value range (`min_value`/`max_value`), mean bounds, outlier ratio, categorical `allowed_values`
- **Referential** — foreign key integrity, join coverage ratio, output file freshness

## Environment variables

| Variable | Service | Default | Description |
|---|---|---|---|
| `DISPATCHER_URL` | observer, runner | `http://localhost:8000` | Dispatcher endpoint |
| `REPO_PATH` | observer, runner | `../tests/sample_pipeline` | Path to watched Git repo |
| `POLL_INTERVAL` | observer | `10` | Seconds between Git polls |
| `RUNNER_ID` | runner | `runner-1` | Unique runner identifier |
| `HEARTBEAT_INTERVAL` | runner | `5` | Seconds between heartbeats |

## Dispatcher API

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Active runners and pending job count |
| `POST` | `/dispatch` | Submit a new validation job |
| `GET` | `/jobs` | List recent jobs |
| `GET` | `/jobs/{job_id}` | Job detail with check results |
| `POST` | `/runners/register` | Register a runner |
| `POST` | `/runners/heartbeat` | Runner keep-alive |
| `GET` | `/runners/job/{runner_id}` | Poll for an assigned job |
| `POST` | `/jobs/result` | Submit check results |
