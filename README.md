# Lunar MineOps AI OS

> Mission Readiness Agent for Lunar ISRU.
> Validate whether an autonomous lunar excavation-to-processing concept closes
> operationally before launch.
>
> **Simulation only. Not flight critical. No hardware control.**

## What this is

Lunar MineOps AI OS is a narrow-scope, fully functional MVP that closes one
end-to-end loop:

```
NASA / PDS public source context  →  seeded lunar ISRU mission
        →  synthetic 30×30 polar site  →  mineability scoring
        →  Claude-generated balanced plan  →  deterministic 168 h simulation
        →  five-dimension readiness verdict (Go / Conditional Go / No-Go)
        →  Claude anomaly response  →  human approvals
        →  Claude-generated mission readiness report (markdown download)
```

The Claude agent runs **server-side only**. The frontend never sees the
Anthropic API key.

## What problem this solves

> "Before we spend millions launching hardware, can we validate whether this
> autonomous lunar excavation-to-processing concept works under terrain,
> power, mobility, processing, autonomy, and anomaly constraints?"

The product produces operator-facing evidence (readiness verdict, telemetry,
risk register, autonomy artifacts, anomaly responses, mission report) so a
mission readiness review board can decide on the concept before hardware
launch.

## Scope

In scope (built):
- One seeded mission ("Shackleton Ridge ISRU Demo")
- One deterministic synthetic lunar polar site (30×30, seedable)
- One balanced plan strategy
- One deterministic hourly simulation engine (168 h)
- One readiness scoring policy (5 dimensions)
- One Anthropic Claude tool-use agent loop with 13 real tools
- One markdown report
- One mission dashboard UX

Out of scope (intentionally not built): user auth, teams, billing,
multi-user collaboration, scenario lab, custom asset editor, raw DEM
ingestion, real rover integration, flight software, hardware control.

## Architecture

```
┌────────────────────────────────┐         ┌──────────────────────────┐
│  Next.js dashboard             │         │  FastAPI backend         │
│  (apps/web, port 3000)         │ ──REST─►│  (apps/api, port 8000)   │
│                                │         │                          │
│  - Landing page                │         │  - SQLite persistence    │
│  - Mission dashboard           │         │  - Source ingestion      │
│  - Recharts                    │         │  - Site generator        │
│                                │         │  - Mineability scoring   │
│  No Anthropic calls here.      │         │  - Balanced planner      │
│  Only NEXT_PUBLIC_API_BASE_URL │         │  - Simulation engine     │
└────────────────────────────────┘         │  - Anomaly + readiness   │
                                           │  - Markdown report       │
                                           │                          │
                                           │   ┌──────────────────┐   │
                                           │   │ Claude tool-use  │   │
                                           │   │ agent loop       │   │
                                           │   │ (13 tools)       │   │
                                           │   └────────┬─────────┘   │
                                           └────────────┼─────────────┘
                                                        │
                                                        ▼
                                              ┌──────────────────┐
                                              │ Anthropic API    │
                                              │ (server-side)    │
                                              └──────────────────┘
                                                ▲
                                                │ httpx + bs4
                                              ┌─┴─────────────┐
                                              │ NASA / PDS    │
                                              │ public pages  │
                                              └───────────────┘
```

## How source ingestion works

The backend fetches six official public pages with `httpx`, strips
`nav/footer/script/style` chrome with BeautifulSoup, classifies sentences
into nine categories (`moon_to_mars_architecture`, `subarchitecture`,
`isru`, `topography_data`, `power`, `mobility`, `autonomy`, `logistics`,
`infrastructure`), and persists each as a `SourceDocument` row with
`fetched_at`, `content_hash`, `is_fallback`. If a fetch fails the backend
inserts a fallback snapshot and clearly labels it. The frontend shows
freshness and the fallback flag.

Sources used:
- https://www.nasa.gov/moontomarsarchitecture/
- https://www.nasa.gov/moontomarsarchitecture-components/
- https://www.nasa.gov/overview-in-situ-resource-utilization/
- https://www.nasa.gov/reference/jsc-in-situ-resource-utilization/
- https://pds-geosciences.wustl.edu/missions/lro/lola.htm
- https://science.nasa.gov/mission/lro/lola/

## How the Claude tool-use agent loop works

`apps/api/app/agents/agent_loop.py` implements the iterative tool-use loop:

1. Build messages: `system` prompt + user prompt + tools.
2. Call `client.messages.create(...)` (real Anthropic SDK in production, a
   scriptable fake client in tests).
3. If Claude returns `tool_use` blocks, validate the tool name and input,
   execute the corresponding backend tool, and append the result as a
   `tool_result` block.
4. Stop when Claude returns final text. Hard cap of 8 iterations.
5. Persist an `AgentRun` row with input prompt, tool calls, and final
   response.

Tools exposed (`apps/api/app/agents/tool_registry.py`):

```
refresh_public_sources            generate_balanced_mission_plan
get_source_context                run_mission_simulation
get_mission_context               get_simulation_details
generate_synthetic_lunar_site     recommend_anomaly_response
score_site_mineability            create_approval
seed_default_assets               generate_autonomy_artifacts
                                  generate_mission_report
```

Each tool maps to real backend logic (no static stubs).

## Required environment variables

`.env.example`:

```
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-6
DATABASE_URL=sqlite:///./lunar_mineops.db
CORS_ORIGINS=http://localhost:3000
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
SOURCE_REFRESH_MODE=live
```

- `ANTHROPIC_API_KEY` is required only for `/agent/*` endpoints. The
  backend boots and serves all deterministic routes without it.
- `NEXT_PUBLIC_API_BASE_URL` is the only env var the frontend reads. It is
  safe to expose. Do not add `ANTHROPIC_API_KEY` to the web container or
  any `NEXT_PUBLIC_*` variable.

## Local development

### Backend

```
cd apps/api
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../../.env.example .env       # add ANTHROPIC_API_KEY here
uvicorn main:app --reload --port 8000
```

Health check: `curl localhost:8000/health` → `{"status":"ok","anthropic_configured":true|false}`.

### Frontend

```
cd apps/web
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

Open http://localhost:3000.

### Docker

```
ANTHROPIC_API_KEY=sk-... docker compose up --build
```

Brings up `api` (port 8000, SQLite volume `api_data`) and `web` (port 3000).

### Tests

```
cd apps/api
. .venv/bin/activate
pytest -q
```

Tests cover source ingestion (with fallback + stub fetcher), site
generation, mineability scoring, asset seeding, planning, simulation,
readiness scoring, anomaly cadence, agent tools, agent loop (using the
fake Anthropic client), and report markdown shape.

### Make targets

```
make install   # set up backend venv + frontend node_modules
make api       # run backend
make web       # run frontend
make test      # run pytest
make seed      # POST /demo/seed via curl
```

## Demo walkthrough

1. Add `ANTHROPIC_API_KEY` to `apps/api/.env`. Set `ANTHROPIC_MODEL=claude-sonnet-4-6`.
2. Run the backend: `cd apps/api && . .venv/bin/activate && uvicorn main:app --reload --port 8000`.
3. Run the frontend: `cd apps/web && npm run dev`.
4. Open http://localhost:3000.
5. Click **Launch Demo Mission**.
6. The dashboard loads with mission, site, assets, and source context (live
   or fallback).
7. Click **Run Mission Readiness Analysis**. Claude will call the source +
   mission tools, generate the plan, run the simulation, and return the
   readiness verdict.
8. Review the five readiness verdict cards (Site, Production, Power,
   Autonomy, Mission).
9. Inspect source context, refresh sources if needed.
10. Inspect the lunar map: toggle layers (mineability, resource, hazard,
    illumination, slope, comms), click cells.
11. Inspect the plan timeline, risk register, and autonomy artifacts.
12. Review production / battery margin / power Recharts.
13. Click **Ask Claude for Response** on any anomaly.
14. Approve or reject any pending approvals (operator note optional).
15. Click **Generate Mission Readiness Report**, then **Download .md**.

## API endpoint overview

| Path | Description |
|---|---|
| `GET /health` | Health + anthropic_configured flag |
| `GET /sources` | List source documents |
| `POST /sources/refresh` | Refresh source documents |
| `GET /sources/context` | Source-grounded facts and freshness |
| `POST /demo/seed` | Idempotent demo mission/site/assets seed |
| `POST /demo/reset` | Wipe all mission-scoped state |
| `GET /demo/default-dashboard` | Snapshot of latest mission state |
| `GET /missions/{id}` | Mission bundle (mission, site, assets, latest plan/sim, anomalies) |
| `GET /missions/{id}/plans` | Plans for mission |
| `GET /plans/{plan_id}` | Plan detail |
| `GET /simulation-runs/{id}` | Simulation summary |
| `GET /simulation-runs/{id}/telemetry` | Telemetry + curves |
| `GET /simulation-runs/{id}/anomalies` | Anomaly list |
| `GET /simulation-runs/{id}/approvals` | Approvals for simulation |
| `POST /approvals/{id}/approve` | Approve with optional operator note |
| `POST /approvals/{id}/reject` | Reject with optional operator note |
| `GET /simulation-runs/{id}/report.md` | Deterministic markdown report |
| `GET /agent/status` | `anthropic_configured`, model, tools |
| `POST /agent/run-readiness-analysis` | Full Claude workflow |
| `POST /agent/anomaly-response` | Claude anomaly response + optional approval |
| `POST /agent/report` | Claude-generated markdown report |
| `POST /agent/refresh-sources` | Claude-driven source refresh |

## Known limitations

- Synthetic terrain. The MVP does not ingest raw LOLA DEM products.
- Public-source context only. No proprietary mission data.
- Simulation only. No hardware control. Autonomy artifacts are draft.
- Single seeded mission with one balanced plan strategy.
- Optional operator chat is intentionally not implemented to keep scope
  narrow.
- Live source fetches depend on the network. Fallback snapshots are used
  on failure.

## Production hardening roadmap

- Replace SQLite with Postgres; add Alembic migrations.
- Add user auth and audit logs for approvals.
- Replace synthetic terrain with LOLA / NAC pipelines.
- Replace JSON snapshots with proper telemetry storage (TimescaleDB or DuckDB).
- Container hardening: rootless, non-root user, read-only FS for `web`.
- Add rate limiting and observability (OpenTelemetry).
- Replace the fake Anthropic test client with VCR-style recording for
  integration tests.
- Add Playwright end-to-end tests for the dashboard.
- Replace the deterministic anomaly cadence with a calibrated risk model.
- Add multi-mission and multi-plan workflows.
- Sign and store agent runs alongside cryptographic provenance.

## Security notes

- The Anthropic API key is read only from `apps/api/.env` and never
  forwarded to the web container.
- The frontend reads only `NEXT_PUBLIC_API_BASE_URL`.
- All Claude calls happen inside FastAPI; frontend talks to FastAPI only.
- No flight-critical commands are emitted. All artifacts are draft.
