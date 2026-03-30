# ─────────────────────────────────────────────────────────────────────────────
# Tiltfile — tutorial-tilt-dev
#
# A Tiltfile is written in Starlark, a Python-like language used by Tilt.
# It is NOT a shell script and NOT a Makefile — it is a declarative description
# of your development environment. Tilt evaluates this file on startup and
# every time it changes on disk (so editing the Tiltfile itself is live too).
#
# Docs: https://docs.tilt.dev/api.html
# ─────────────────────────────────────────────────────────────────────────────


# ─── STEP 1: Load Docker Compose ─────────────────────────────────────────────
#
# docker_compose() is almost always the first call in a Tiltfile when your
# project already has a docker-compose.yml. Tilt reads:
#   - service names         → become Tilt "resources"
#   - ports (host:container)→ forwarded automatically, shown in the UI
#   - depends_on            → used as a fallback dependency hint
#   - environment / volumes → passed through unchanged to Docker
#
# You do NOT need to duplicate any of that here. Tilt wraps Compose; it does
# not replace it. Your existing `docker compose up` workflow still works
# independently — Tilt just adds live-reload and the UI on top.
#
# Accepts a single path or a list for multiple override files, e.g.:
#   docker_compose(["docker-compose.yml", "docker-compose.override.yml"])
docker_compose("./docker-compose.yml")


# ─── STEP 2: Override image builds with docker_build() ───────────────────────
#
# When Tilt sees a `build:` section in docker-compose.yml it would normally
# just run `docker build` like plain Compose does — a full rebuild every time.
#
# docker_build() intercepts that and gives Tilt control over the build so it
# can apply smarter strategies, most importantly: live_update.
#
# Signature:
#   docker_build(image_name, context_path, live_update=[...])
#
#   image_name   — must exactly match the image name Compose assigns to the
#                  service. Run `docker compose config` to see resolved names.
#                  Typically: "<folder_name>-<service_name>" e.g. "tutorial-tilt-dev-app"
#   context_path — the Docker build context (same as `build: ./app` in Compose)
#   live_update  — ordered list of steps applied to the RUNNING container
#                  instead of rebuilding the image. This is the key feature.
#
# Without live_update: every file save → full docker build → container restart (~10-30s)
# With    live_update: every file save → sync files in-place                  (~200ms)

docker_build(
    "tutorial-tilt-dev-app",   # image name — must match what Compose uses
    "./app",                    # build context (where the Dockerfile lives)
    live_update=[
        # ── live_update step 1: sync ──────────────────────────────────────────
        # sync(src, dest) copies any changed file from src (on the host) to
        # dest (inside the running container). Tilt watches the src directory
        # for inotify events and only sends the diff — not the whole directory.
        #
        # Here: any .py or other file changed under ./app/ on your laptop
        # appears immediately at /app/ inside the container.
        sync("./app", "/app"),

        # ── live_update step 2: run ───────────────────────────────────────────
        # run(cmd, trigger=[...]) executes a shell command INSIDE the container
        # but ONLY when one of the trigger files changes.
        #
        # trigger= is a list of file paths (relative to the Tiltfile). Tilt
        # runs the command when any of those files appears in the current diff.
        # Without trigger=, the command would run on every single file change.
        #
        # Why pip install here? If requirements.txt changes, new packages need
        # to be installed before the app can import them. The sync above already
        # copied the new requirements.txt, so pip can read it from /app/.
        run(
            "pip install -r /app/requirements.txt",
            trigger=["./app/requirements.txt"],
        ),

        # ── No restart_container() for the app ───────────────────────────────
        # uvicorn is started with --reload (see Dockerfile CMD), so it watches
        # /app for .py changes itself and reloads the Python process in-place.
        # Adding restart_container() here would be redundant and slower.
    ],
)

docker_build(
    "tutorial-tilt-dev-worker",
    "./worker",
    live_update=[
        # Same sync pattern: keep /app/ inside the worker container in sync
        # with ./worker/ on the host at all times.
        sync("./worker", "/app"),

        # Install new dependencies when requirements.txt changes.
        run(
            "pip install -r /app/requirements.txt",
            trigger=["./worker/requirements.txt"],
        ),

        # ── restart_container() ───────────────────────────────────────────────
        # restart_container() is the last live_update step. It sends a SIGTERM
        # to PID 1 inside the container and waits for it to exit, then Tilt
        # restarts it (Docker keeps the container alive).
        #
        # The worker is a plain while-loop with no file watching, so it will
        # never pick up source changes on its own. restart_container() is the
        # correct choice here. It runs after every sync, so every .py edit
        # triggers a restart — fast because no image rebuild happens.
        restart_container(),
    ],
)


# ─── STEP 3: Configure resources with dc_resource() ──────────────────────────
#
# dc_resource() does NOT start or build anything — it annotates a service that
# was already declared by docker_compose() above. Think of it as metadata.
#
# Common parameters:
#   labels        — groups resources visually in the Tilt UI sidebar
#   resource_deps — explicit start ordering; Tilt waits until the listed
#                   resources are "ready" before starting this one
#   readiness_probe — custom health check Tilt uses to decide "ready"
#   links         — clickable URLs shown in the resource's UI panel
#   auto_init     — False = resource is disabled until manually triggered

# redis: infrastructure layer — starts first, no dependencies
dc_resource(
    "redis",
    labels=["infra"],   # shown under the "infra" group in the UI

    # readiness_probe tells Tilt when redis is truly ready to accept connections.
    # Without this, Tilt would consider redis "ready" as soon as the container
    # starts — but redis needs ~1s to initialize before it can accept commands.
    #
    # probe() parameters:
    #   period_secs     — how often to run the check
    #   initial_delay_secs — wait before the first check (default 0)
    #   exec            — run a command inside the container; exit 0 = healthy
    #   http_get        — alternative: poll an HTTP endpoint
    readiness_probe=probe(
        period_secs=5,
        exec=exec_action(["redis-cli", "ping"]),
        # exec_action runs ["redis-cli", "ping"] inside the redis container.
        # redis-cli ping returns "PONG" and exits 0 when Redis is ready.
    ),
)

# app: depends on redis being ready before it starts
dc_resource(
    "app",
    labels=["backend"],

    # resource_deps is Tilt's dependency graph. Tilt will not start "app" until
    # "redis" passes its readiness_probe above.
    # This is more reliable than Compose's depends_on + condition: service_healthy
    # because Tilt re-checks on restarts and live-updates too.
    resource_deps=["redis"],

    # links appear as clickable buttons in the Tilt UI resource panel.
    # They do not affect behaviour — purely for developer convenience.
    links=[
        link("http://localhost:8000",       "API root"),
        link("http://localhost:8000/docs",  "Swagger UI"),   # FastAPI auto-generates this
        link("http://localhost:8000/health","Health check"),
    ],
)

# worker: also depends on redis, no links needed (it has no HTTP interface)
dc_resource(
    "worker",
    labels=["backend"],
    resource_deps=["redis"],  # worker.py connects to Redis on startup; wait for it
)


# ─── STEP 4: local_resource() — run host commands inside Tilt ────────────────
#
# local_resource() runs a command on the HOST MACHINE (your laptop), not inside
# any container. It appears as a resource in the Tilt UI just like a service,
# with its own log panel, status indicator, and trigger button.
#
# Use cases:
#   - Integration test suites (this example)
#   - Code generators (protobuf, openapi clients, etc.)
#   - Linters / formatters
#   - Database migrations (run before the app starts)
#   - Any CLI tool you don't want to bake into a container image
#
# config.main_dir is a Tilt built-in: the directory containing the Tiltfile.
# Using it makes the path work regardless of where you run `tilt up` from.

local_resource(
    "tests",
    # cmd is the shell command to run. It runs in a subprocess on the host.
    # APP_URL tells the test suite where to find the running app.
    cmd="cd {} && APP_URL=http://localhost:8000 pytest tests/ -v".format(config.main_dir),

    # resource_deps ensures Tilt waits for "app" to be ready before this
    # resource is allowed to run. Without this, tests would fail immediately
    # because the app container might not be listening yet.
    resource_deps=["app"],

    labels=["test"],   # shown under a "test" group in the UI

    # auto_init=False means this resource does NOT run automatically when
    # `tilt up` starts. You trigger it manually (see below).
    # Change to True if you want tests to run on every file change.
    auto_init=False,

    # trigger_mode controls when Tilt re-runs this resource:
    #   TRIGGER_MODE_MANUAL — only when you press "Run" in the UI or run
    #                         `tilt trigger tests` in a terminal
    #   TRIGGER_MODE_AUTO   — re-runs whenever any watched file changes
    #                         (combine with serve_dir= or deps= to scope it)
    trigger_mode=TRIGGER_MODE_MANUAL,
)
