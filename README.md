Each component runs as an independent Docker container. The dispatcher is the only stateful service — it persists job history and runner registry to SQLite. Runners are stateless and horizontally scalable.

## Tech Stack

| Layer | Technology |
|---|---|
| API | Python 3.11, FastAPI, Uvicorn |
| Persistence | SQLAlchemy, SQLite |
| Validation | Pandas, Pandera, NumPy, PyArrow |
| Git integration | GitPython |
| Containerization | Docker, Docker Compose |
| Frontend | React, Vite, TailwindCSS, Axios |

## Quick Start

**Prerequisites:** Docker Desktop, Git

```bash
git clone https://github.com/OJP-BIT/dataflow-ci.git
cd dataflow-ci
docker compose up --build
```

Dashboard: `http://localhost:3000`
API docs: `http://localhost:8000/docs`

## Defining Expectations

Add a `dataflow_expectations.yml` file to your pipeline repository:

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
      allowed_values:
        - pending
        - shipped
        - delivered
    quantity:
      min_value: 1
      max_value: 10000
      mean_min: 1.0
      mean_max: 500.0
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

## Fault Recovery

The dispatcher runs a background heartbeat monitor checking runner liveness every 10 seconds. If a runner stops sending heartbeats for 30 seconds, it is marked dead and its in-progress job is automatically reassigned to another available runner.

## Scaling

To add more parallel runners, extend `docker-compose.yml`:

```yaml
runner-3:
  build: ./runner
  environment:
    - RUNNER_ID=runner-3
    - DISPATCHER_URL=http://dispatcher:8000
```

## Project Structure
