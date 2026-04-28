# Podman Local Compatibility Runbook

This runbook is for students who cannot install Docker Desktop on a company
machine. It keeps the course source code unchanged and treats Podman as an
alternative local container runtime.

The primary course path is still Docker Compose. Podman support is a
best-effort compatibility path because `podman compose` delegates to an external
Compose provider and is not guaranteed to behave identically to Docker Compose.

## Current Compatibility Position

Project compose features that need validation on Podman:

| Compose feature | Used by this repo | Expected Podman risk |
|---|---:|---|
| Named volumes | PostgreSQL, MinIO, Dagster, Phoenix | Low |
| Bridge network + service DNS | `postgres`, `minio`, APIs, Dagster | Low |
| Build contexts | `rag_api`, `tool_api`, `devbox`, simulator | Medium on locked-down Macs |
| Bind mounts under user home | source code, manifests, contracts | Low if repo is under home directory |
| `healthcheck` | PostgreSQL, MinIO, APIs | Medium with older providers |
| `depends_on.condition` | health-gated service startup | Medium with older providers |
| `profiles` | `devbox` tools path | Medium with older providers |
| Fixed `container_name` | all major services | Medium if stale Podman containers exist |
| `restart: unless-stopped` | long-running services | Low for class labs; restart-on-boot is not required |

Local branch validation on 2026-04-28:

| Check | Result |
|---|---|
| Host | macOS Apple Silicon, Podman machine with 4 CPU / 8 GB RAM / 60 GB disk |
| Podman | `podman version 5.8.2` |
| Compose provider | Default `podman compose` provider used Docker Compose v2; `podman-compose 1.5.0` also parsed config |
| Docker Compose config parse | Passed with `docker compose ... config` |
| Podman Compose config parse | Passed with both default provider and `podman-compose` provider |
| Direct Podman pull from Docker Hub | Failed once with `registry-1.docker.io` timeout on `python:3.11-slim` |
| Devbox build | Passed after base image was available in Podman |
| Week01/Week02 contract tests | `44 passed` |
| Week02 manifest gate | Passed; 3 manifests valid, 9 assets accepted |
| Week05 dbt parse | Passed |
| Week05 dbt build | `PASS=37 WARN=0 ERROR=0 SKIP=0 TOTAL=37` |
| Full pytest | `65 passed, 2 skipped` |
| Podman services | `postgres`, `minio`, `rag_api`, `tool_api`, `dagster`, `otel_collector`, `phoenix` started |
| HTTP smoke | RAG `200`, Tool API `200`, MinIO `200`, Dagster `200` after warmup, Phoenix `200` |

Important interpretation:

- The repo does not need a separate Podman source tree.
- The compose file itself is compatible with Podman on the tested Mac.
- First-time setup still depends on registry/package network access:
  Docker Hub for base images, Debian apt repositories, and PyPI.
- In locked-down company networks, students may need an approved registry mirror
  or preloaded course images. That is an environment distribution issue, not a
  source-code fork issue.

## Option A: Podman Desktop Path

Use this when students are allowed to install Podman Desktop but not Docker
Desktop.

1. Install Podman Desktop from the official site or approved internal software
   center.
2. Start a Podman machine from Podman Desktop.
3. Enable Docker compatibility if the student wants third-party Docker tooling.
4. Enable Compose support from Podman Desktop settings if `podman compose` is
   not already available.

Verify:

```bash
podman --version
podman machine list
podman compose version
```

## Option B: Podman CLI Path

Use this on macOS only if command-line installation is allowed.

```bash
brew install podman podman-compose

podman machine init --cpus 4 --memory 8192 --disk-size 60
podman machine start

podman --version
podman machine list
podman compose version
```

If `podman compose` cannot find a Compose provider:

```bash
export PODMAN_COMPOSE_PROVIDER="$(command -v podman-compose)"
podman compose version
```

If `podman compose` prints a message similar to:

```text
Executing external compose provider "/usr/local/bin/docker-compose"
```

that is expected. Podman is using an external Compose provider while wiring it
to the Podman socket. If that provider works, keep it. Only force
`podman-compose` when the default provider is unavailable or broken.

If Homebrew is blocked by the Xcode license, an admin must accept the license on
that machine:

```bash
sudo xcodebuild -license accept
```

Do not make this a course requirement. It is a local machine administration
step.

## Project Smoke Test

Run these commands from the repo root.

```bash
cp infra/env/.env.example infra/env/.env.local
```

First validate the Compose file without starting services:

```bash
podman compose --env-file infra/env/.env.local -f infra/docker-compose.yml config
```

If Docker Desktop services from a previous lab are still running, stop them
before starting the Podman stack because the same host ports are used:

```bash
docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml down
```

This does not remove Docker volumes unless `-v` is added.

Start the stateful Week01 base:

```bash
podman compose --env-file infra/env/.env.local -f infra/docker-compose.yml \
  up -d --build postgres minio minio_init
```

Check service state:

```bash
podman compose --env-file infra/env/.env.local -f infra/docker-compose.yml ps
podman logs omni_postgres --tail 80
podman logs omni_minio --tail 80
```

Build the course devbox:

```bash
podman compose --profile tools --env-file infra/env/.env.local \
  -f infra/docker-compose.yml build devbox
```

Run the contract baseline:

```bash
podman compose --profile tools --env-file infra/env/.env.local \
  -f infra/docker-compose.yml run --rm devbox pytest tests/contract/ -q
```

Run the Week02 manifest gate smoke test:

```bash
podman compose --profile tools --env-file infra/env/.env.local \
  -f infra/docker-compose.yml run --rm devbox \
  python -m pipelines.ingestion.seed_loader \
    --manifest-path data/seed_manifests/manifest_edge_gateway_pdf_v1.json \
    --manifest-path data/seed_manifests/manifest_tickets_synthetic_v1.json \
    --manifest-path data/seed_manifests/manifest_workspace_helpcenter_v1.json
```

Run the Week05 dbt parser and connection checks after PostgreSQL is healthy:

```bash
podman compose --profile tools --env-file infra/env/.env.local \
  -f infra/docker-compose.yml run --rm devbox \
  bash -lc 'cd analytics && DBT_PROFILES_DIR=. dbt parse'
```

If the full database path is required:

```bash
podman compose --profile tools --env-file infra/env/.env.local \
  -f infra/docker-compose.yml run --rm devbox \
  bash -lc 'cd analytics && DBT_PROFILES_DIR=. dbt build --select tag:week05'
```

Expected pass criteria:

| Area | Pass signal |
|---|---|
| Compose parser | `config` exits 0 |
| Base services | `postgres` and `minio` are running or healthy |
| Devbox | image builds and can import project packages |
| Contracts | contract tests pass |
| Week02 gate | seed manifests validate and emit gate output |
| Week05 dbt | `dbt parse` passes; `dbt build` passes after seed data exists |

Full stack smoke test:

```bash
podman compose --env-file infra/env/.env.local -f infra/docker-compose.yml up -d --build

curl -s http://localhost:8000/health
curl -s http://localhost:8001/health
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:9000/minio/health/live
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3000
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:6006
```

Dagster may return `503` for a short warmup window. Wait 20-30 seconds and
retry `http://localhost:3000`.

Week05 Tool API smoke test after `dbt build`:

```bash
curl -s -X POST http://localhost:8001/api/v1/tools/query_support_kpis \
  -H 'Content-Type: application/json' \
  -d '{
    "actor_role": "instructor",
    "actor_id": "podman-smoke",
    "metrics": ["ticket_count"],
    "date_from": "2026-04-01",
    "date_to": "2026-04-28",
    "limit": 10
  }'
```

Expected shape:

```json
{
  "allowed": true,
  "rows": [],
  "denial_code": null
}
```

An empty `rows` array is acceptable when the local Podman PostgreSQL volume has
not been loaded with seed data yet.

## Hostname Rules

Inside containers, keep service hostnames as Compose service names:

```text
postgres:5432
minio:9000
```

Examples:

```text
DATABASE_URL=postgresql://omni:omnipass@postgres:5432/omnisupport
MINIO_ENDPOINT=http://minio:9000
DBT_POSTGRES_HOST=postgres
ICEBERG_S3_ENDPOINT=http://minio:9000
```

Only switch to `localhost` for host-native commands that run outside
containers. The default course commands run inside `devbox`, so they should keep
the Compose service names.

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `podman: command not found` | Podman is not installed | Install Podman Desktop or Podman CLI |
| `looking up compose provider failed` | No Compose provider | Install/enable Podman Compose support or set `PODMAN_COMPOSE_PROVIDER` |
| `registry-1.docker.io ... i/o timeout` | Podman VM cannot reach Docker Hub | Retry on a stable network or use an approved image mirror/preloaded images |
| `pypi.org ... ReadTimeoutError` | Podman build cannot reliably reach PyPI | Retry, use a company PyPI mirror, or prebuild course images |
| Port `9000`, `9001`, `3000`, `6006`, `8000`, or `8001` is busy | Docker or old Podman services are already running | Stop the conflicting runtime before the lab |
| `container name is already in use` | Stale Podman container with fixed `container_name` | Run `podman rm -f omni_postgres omni_minio omni_dagster omni_rag_api omni_tool_api omni_devbox` |
| Services start before dependencies are healthy | Older Compose provider ignores `depends_on.condition` | Wait for `postgres` and `minio`, then rerun the failed command |
| Bind mount is empty inside container | Podman machine path sharing issue | Keep the repo under the user home directory and restart Podman machine |
| `permission denied` under named volumes | Rootless volume ownership mismatch | Recreate only the affected Podman volumes for a clean lab |
| dbt cannot connect to PostgreSQL | Running dbt on host instead of in `devbox` | Use the documented `podman compose ... run --rm devbox ...` command |

Clean up after a Podman lab:

```bash
podman compose --env-file infra/env/.env.local -f infra/docker-compose.yml down
```

To remove local lab data:

```bash
podman compose --env-file infra/env/.env.local -f infra/docker-compose.yml down -v
```

## When Not To Use Podman

Use the Docker path or a provided teaching VM if:

- company policy blocks both Docker Desktop and Podman Desktop;
- local virtualization is disabled;
- the student cannot allocate at least 4 CPUs, 8 GB memory, and 25 GB disk to
  the Podman machine;
- the class needs instructor-grade screenshots with exactly matching Docker
  Desktop UI behavior.
