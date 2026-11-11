# CryoNexa

CryoNexa is a cold-chain operations dashboard and deterministic data pipeline for monitoring temperature and humidity across pharmaceutical storage and transport journeys. It highlights shipment exceptions, excursion evidence, custody timelines, calibration warnings, and corrective actions.
"Cryo" represents cold environments; "Nexa" suggests connected intelligence.

## Architecture

- `frontend/` — React + Vite operations dashboard.
- `backend/` — FastAPI operations API and deterministic synthetic-data generator.
- `database/` — SQLite relational schema and field-level data dictionary.
- `data/generated/` — reproducible CSV/JSON exports and a local SQLite database (generated locally, not committed).

SQLite is used for zero-setup local development. The schema contains standard relational constraints plus SQLite-specific setup; production PostgreSQL deployment should use an equivalent PostgreSQL migration. The API uses operational tables only. The ground-truth sidecar is kept separate and is not an API feature.

## Run locally

Requirements: Python 3.11+ and Node.js 18, 20, or 22+.

1. Generate a small starter dataset (defaults to 36 shipments, fixed seed `20261022`):

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   python -m app.generate
   ```

   To make the full requested dataset of 1,000 shipments and 300 containers:

   ```powershell
   python -m app.generate --shipments 1000 --containers 300 --seed 20261022 --output ..\data\generated\full-scale-demo
   ```

   The same generator and seed drive both scales. Shipments are distributed across a bounded one-day departure window and the simulation has a fixed six-day reference time, preventing larger datasets from drifting into future calendar years. To run the API against the full-scale database without replacing the starter dataset:

   ```powershell
   $env:CRYONEXA_DB = (Resolve-Path ..\data\generated\full-scale-demo\cryo.db).Path
   uvicorn app.main:app --reload
   ```

   Use `--output <path>` to choose another export directory.

2. Start the API from the `backend` directory:

   ```powershell
   uvicorn app.main:app --reload
   ```

   API docs: <http://localhost:8000/docs>. Health: <http://localhost:8000/api/health>. Corrective actions can move from `open` to `in_progress` and then `completed`; each change is persisted as an append-only status event.

3. In a separate terminal, install and start the dashboard:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

   Open <http://localhost:5173>.

The generated database location can be overridden with `CRYONEXA_DB`; browser origins can be configured using comma-separated `CORS_ORIGINS`.

## Dashboard navigation

The sidebar and dashboard summary cards open live, paginated views for shipments, containers, sensors, excursions, corrective actions, and product compliance. The notification bell opens the notification list; record IDs open a detail dialog, and corrective-action details include their append-only status history. Search supports `Ctrl+K`/`Cmd+K`, and dashboard list pages can be refreshed without losing their current page.

The Overview includes an hourly last-24-hour temperature/humidity trend and a reading, sensor, excursion, quality, data-gap, and compliance snapshot. The generator persists these derived aggregates, including product-level compliance counts, so the overview and Compliance Center do not repeatedly scan the full reading history; older databases rebuild the snapshot automatically when its latest-reading key does not match or product aggregates are absent. The overview's time window ends at the newest available reading in the dataset rather than the computer clock. It also shows the newest reading's UTC timestamp and age relative to the API clock, so seeded historical data is not presented as current telemetry. The overview labels synthetic data explicitly; averages across journeys are informational, while compliance is evaluated against each reading's product policy.

The API exposes `/api/shipments`, `/api/containers`, `/api/sensors`, `/api/excursions`, `/api/actions`, `/api/compliance`, and `/api/notifications`. List endpoints accept `limit` and `offset` query parameters and return an `items` array with the total record `count`.

Open any container record to inspect its latest 288 readings (24 hours at the standard five-minute interval), with temperature and humidity charts, policy threshold bands, reading-quality flags, paginated history, and linked excursions. The API endpoint `/api/containers/{container_id}/monitoring` returns those readings together with the product policy applied to each one and the container's excursion history.

## Docker

From the project root, run `docker compose up --build`. The API service generates a 36-shipment starter dataset before serving the UI and API.

## Data pipeline and rules

1. Generate products and product-specific, effective-dated temperature/humidity policies first, followed by containers and calibrated sensors.
2. Generate shipments, container/sensor assignments, four-stop route plans, and append-only status/custody events using parent IDs.
3. Emit temperature and humidity sensor readings on a fixed five-minute cadence over deterministic two-to-five-day trips. Temperature/humidity deviations, dropouts, route delays, expired calibration, and negative scenarios are reproducible from the seed.
4. Detect excursions against the corresponding temperature or humidity policy, derive duration from the reading interval, compare it with the product's permissible duration, and create corrective actions and notifications based on the decision.
5. Export operational CSV files, `cryo.db`, `seed.sql`, `ground_truth.csv/json`, `validation_summary.json`, `source_manifest.json`, and SHA-256 `checksums.json`. To load the SQL export, apply `database/schema.sql` first and then `seed.sql`. The ground-truth sidecar never enters the operational database.

The intentional negative scenarios include physically impossible temperature, missing intervals (not considered safe), delivery before departure, a policy/product mismatch, and an under-reported excursion duration. Each affected record is labelled and represented in ground truth. These known issues are excluded from baseline quality assumptions rather than silently changing unrelated records.

## Validation and tests

From the `backend` directory:

```powershell
python -m unittest discover -s tests -v
```

The generator checks deterministic primary keys, foreign keys and join consistency, lifecycle transitions, date order, custody ordering, five-minute reading gaps, duration reconciliation, physical/humidity ranges, and anomaly labels before writing data. Its validation summary includes coverage counts for calibration, shipment states, delays, excursion severities/durations, and injected issue types. SQLite foreign-key checks run after import. A test regenerates the same small dataset twice and compares the resulting structured records and file checksums.

## Reproducibility

The default seed is `20261022`. Generation uses a local `random.Random(seed)`, a fixed UTC anchor/reference time, stable entity ordering, and deterministic IDs. Re-run the same command into two separate output folders and compare their `checksums.json` files to verify byte-for-byte output reproducibility. The SQLite database is excluded from Git along with generated datasets.

## Public data and provenance

All demo data is synthetic and generated in this repository; no external dataset, private information, or third-party source is used. `source_manifest.json` records this provenance, seed, generator version, and generated record counts. No external data license or attribution is applicable.
