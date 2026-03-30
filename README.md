# Tilt + Docker Compose Tutorial

A hands-on tutorial for [Tilt](https://tilt.dev/) — the local development environment that wraps Docker Compose with live reload, a real-time UI, and smarter dependency management.

## What you will build

A three-service stack:

| Service | Description | Port |
|---------|-------------|------|
| **app** | FastAPI web server with a Redis-backed counter | `8000` |
| **worker** | Background process that logs the counter every 10 s | — |
| **redis** | Redis 7 (shared state) | `6379` |

By the end you will know how to:
- Boot a multi-service stack with `tilt up`
- Edit code and watch it reload inside the container **without** rebuilding the image
- Use the Tilt UI to view logs, trigger tests, and manage services

---

## Prerequisites

| Tool | Install |
|------|---------|
| Docker Desktop (or Colima) | https://www.docker.com/products/docker-desktop |
| Tilt | `curl -fsSL https://raw.githubusercontent.com/tilt-dev/tilt/master/scripts/install.sh \| bash` |
| Python 3.12+ (for running tests locally) | https://python.org |
| pytest + httpx | `pip install pytest httpx` |

Verify installation:

```bash
tilt version        # v0.33+
docker compose version
```

---

## Project layout

```
tutorial-tilt-dev/
├── Tiltfile                  # Tilt configuration (the main thing to learn)
├── docker-compose.yml        # Standard Compose file (Tilt reads this)
├── app/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py               # FastAPI app
├── worker/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── worker.py             # Background worker
└── tests/
    └── test_app.py           # Integration test suite
```

---

## Part 1 — Plain Docker Compose (baseline)

Before using Tilt, understand the baseline. Start the stack the normal way:

```bash
docker compose up --build
```

Try the API:

```bash
curl http://localhost:8000/
curl http://localhost:8000/health
curl -X POST http://localhost:8000/count/increment
curl http://localhost:8000/count
```

Now edit `app/main.py` — change the `"message"` string in the root endpoint.
Notice: **nothing updates** until you run `docker compose up --build` again.

Stop it:

```bash
docker compose down
```

---

## Part 2 — Start with Tilt

```bash
tilt up
```

Tilt opens a browser at **http://localhost:10350** — the Tilt UI.

What you see in the UI:
- **redis** (green) — started first, health-checked automatically
- **app** (green) — started after redis was ready
- **worker** (green) — also waits for redis
- **tests** (grey, manual) — ready to run on demand

### Key difference from `docker compose up`

With plain Compose, all services start in parallel regardless of health.
Tilt respects `resource_deps` in the `Tiltfile`, so `app` and `worker` only
start once redis passes its readiness probe.

---

## Part 3 — Live Update (the main feature)

### 3a. Python source file sync

Open `app/main.py` and change the root message:

```python
# before
return {"message": "Hello from Tilt tutorial!", "status": "ok"}

# after
return {"message": "Hello — live update works!", "status": "ok"}
```

Save the file. Watch the Tilt UI — the **app** resource shows a brief sync
indicator, then turns green again. No rebuild. No container restart.

Verify:

```bash
curl http://localhost:8000/
# {"message":"Hello — live update works!","status":"ok"}
```

**How it works**: `sync("./app", "/app")` in the `Tiltfile` copies the changed
`.py` file directly into the running container. `uvicorn --reload` detects the
change and reloads the module.

### 3b. Worker restart on change

Edit `worker/worker.py` — change the log message:

```python
print(f"[worker] current counter = {count}", flush=True)
# change to:
print(f"[worker] COUNTER VALUE: {count}", flush=True)
```

Save. Tilt syncs the file and calls `restart_container()` because the worker
has no built-in hot-reload. Check the worker logs in the Tilt UI — the new
message appears within seconds.

### 3c. Dependency change triggers pip install

Edit `app/requirements.txt` and add a new (harmless) package comment:

```
# added a comment to trigger the run() step
fastapi==0.115.0
...
```

Save. Tilt runs `pip install -r /app/requirements.txt` inside the container
before syncing, because `trigger=["./app/requirements.txt"]` is set.

---

## Part 4 — Running tests from Tilt

The `tests` resource is configured as manual (`auto_init=False`).

**Option A — Tilt UI**: Click the **tests** resource, then press the **▶ Run**
button (or press `r` with the resource selected).

**Option B — terminal**:

```bash
tilt trigger tests
```

Watch the test output stream live in the Tilt UI log panel.

Run them directly outside Tilt at any time:

```bash
APP_URL=http://localhost:8000 pytest tests/ -v
```

Expected output:

```
tests/test_app.py::TestHealth::test_root_returns_ok PASSED
tests/test_app.py::TestHealth::test_health_endpoint_reports_healthy PASSED
tests/test_app.py::TestCounter::test_reset_then_get_returns_zero PASSED
tests/test_app.py::TestCounter::test_increment_increases_by_one PASSED
tests/test_app.py::TestCounter::test_multiple_increments_accumulate PASSED
tests/test_app.py::TestCounter::test_reset_clears_accumulated_count PASSED

6 passed in ...s
```

---

## Part 5 — Tiltfile concepts explained

Read `Tiltfile` alongside this section.

### `docker_compose()`

```python
docker_compose("./docker-compose.yml")
```

Tells Tilt to read service definitions, port mappings, and `depends_on` from
your existing Compose file. You don't rewrite anything — Tilt wraps it.

### `docker_build()` with `live_update`

```python
docker_build(
    "tutorial-tilt-dev-app",
    "./app",
    live_update=[
        sync("./app", "/app"),
        run("pip install ...", trigger=["./app/requirements.txt"]),
    ],
)
```

Replaces Compose's `build:` block. `live_update` defines a sequence of
in-place operations applied to the *running* container instead of rebuilding:

| Primitive | What it does |
|-----------|-------------|
| `sync(src, dest)` | Copies changed files from host into container |
| `run(cmd, trigger=[...])` | Runs a shell command in the container when trigger files change |
| `restart_container()` | Restarts the container process (for apps without hot-reload) |

### `dc_resource()`

```python
dc_resource("app", labels=["backend"], resource_deps=["redis"], links=[...])
```

Configures a Compose service within Tilt:

- `labels` — group related resources in the UI
- `resource_deps` — explicit startup ordering
- `links` — clickable URLs shown in the UI panel
- `readiness_probe` — custom health check logic

### `local_resource()`

```python
local_resource("tests", cmd="pytest tests/ -v", resource_deps=["app"], auto_init=False)
```

Runs a command on the **host** (not inside any container). Useful for:
- Test suites
- Code generators
- Linters / formatters
- Any CLI tool you don't want to containerize

`TRIGGER_MODE_MANUAL` means it only runs when you explicitly trigger it.
Change to `TRIGGER_MODE_AUTO` to run on every file change.

---

## Part 6 — Tilt UI tour

| Area | Description |
|------|-------------|
| Resource list (left) | All services + local resources; green = healthy, red = error |
| Log panel (right) | Streaming logs for the selected resource |
| Status bar | Global build/sync status |
| Header buttons | `tilt up` / `tilt down` controls, filter by label |

Keyboard shortcuts:
- `↑ ↓` — navigate resources
- `r` — trigger selected resource
- `l` — focus log panel
- `?` — show all shortcuts

---

## Part 7 — Stopping

```bash
# Stop Tilt but leave containers running
Ctrl+C

# Stop Tilt AND tear down all containers
tilt down
```

Unlike `docker compose up`, hitting `Ctrl+C` in Tilt does **not** stop your
containers. This is intentional — Tilt is a control plane, not the containers
themselves. Always run `tilt down` when you are done.

---

## Test cases summary

| Test | File | What it validates |
|------|------|-------------------|
| `test_root_returns_ok` | `tests/test_app.py` | Root endpoint returns HTTP 200 and `status: ok` |
| `test_health_endpoint_reports_healthy` | `tests/test_app.py` | `/health` confirms Redis is reachable |
| `test_reset_then_get_returns_zero` | `tests/test_app.py` | Counter resets to 0 |
| `test_increment_increases_by_one` | `tests/test_app.py` | Single increment returns count = 1 |
| `test_multiple_increments_accumulate` | `tests/test_app.py` | Five increments → count = 5 |
| `test_reset_clears_accumulated_count` | `tests/test_app.py` | Reset after increments returns 0 |

---

## Troubleshooting

**`Error: no such image`** — make sure the image name in `docker_build()` exactly
matches the name Compose assigns. Run `docker compose config` to see the
resolved image names.

**Port already in use** — another process holds `8000` or `6379`. Run
`lsof -i :8000` to find it, or change the host port in `docker-compose.yml`.

**Live update not triggering** — check that the file path in `sync()` matches
where you are saving. Paths are relative to the `Tiltfile`.

**Tests fail with connection error** — the app container is not yet ready.
Wait for the **app** resource to turn green in the Tilt UI, then re-trigger.

---

## Next steps

- Add `TRIGGER_MODE_AUTO` to the tests resource so tests run on every code change
- Explore [Tilt Extensions](https://github.com/tilt-dev/tilt-extensions) for
  Helm, Pulumi, and more
- Try `tilt ci` for running the full stack in CI pipelines
- Read the [Tiltfile API reference](https://docs.tilt.dev/api.html)
