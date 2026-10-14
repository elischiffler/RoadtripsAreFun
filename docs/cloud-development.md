# Disposable cloud development

Use Python 3.12, Node 24 and the checks in `AGENTS.md`. Install backend requirements
into a workspace virtual environment and Ruff 0.16.7; run `npm ci` in `frontend`.
Never copy production credentials into this workflow. Keep caches outside the
checkout. Existing workspace CA/proxy settings must remain intact.

## Nested Docker dependency downloads

The October 14 cloud environment can run Docker, but its default Docker config
is read-only. Use a writable per-command config directory, for example
`DOCKER_CONFIG=/workspace/roadtrips-docker`. This does not change daemon settings.
Nested builds could not resolve package hosts. `--network host` plus built-in
`--build-arg HTTP_PROXY --build-arg HTTPS_PROXY` still could not resolve the proxy;
a temporary proxy host mapping reached it but encountered an untrusted proxy CA
inside the pinned image. Do not disable TLS verification or install private
certificates into production images to clear this gate.

`scripts/cloud_build.py` provides a separate offline build path. Download locked
packages using the workspace's existing verified HTTPS transport first:

```sh
python3.12 -m venv /workspace/roadtrips-venv
/workspace/roadtrips-venv/bin/pip install -r backend/requirements.txt ruff==0.16.7
mkdir -p /workspace/cloud-build-cache/wheels
/workspace/roadtrips-venv/bin/pip download --only-binary=:all: \
  --dest /workspace/cloud-build-cache/wheels -r backend/requirements.txt
(cd frontend && npm ci --cache /workspace/.npm-cache)
```

Use Linux Python 3.12 wheels matching the Docker architecture; packages without
compatible wheels fail explicitly. The helper derives a temporary Dockerfile
from the committed one and changes only dependency installation to read a named
build-context cache. Build steps use `--network none`. Runtime stages, pinned base
images, application source, non-root users and security defaults remain unchanged.
The cloud checkout also has mode `0600` source files; root-owned image copies
would otherwise be unreadable by the runtime app/nginx users. The helper stages
Git-visible inputs under ignored `.artifacts/`, normalizes only those temporary
copies to `0644` files/`0755` directories (preserving tracked executable files),
and excludes ignored paths, environment files and symlinks. Host file modes and
production Dockerfiles are untouched. The temporary context is deleted afterward.
Registry/base-image retrieval still requires Docker registry access. Cache mounts
and temporary Dockerfiles are not shipped in runtime images. npm may write inside
its ephemeral bind mount; those writes are discarded by BuildKit.

```sh
python scripts/cloud_build.py backend-test \
  --cache /workspace/cloud-build-cache/wheels \
  --docker-config /workspace/roadtrips-docker \
  --tag roadtrips-crud-test-runner:local --revision local-crud-test
python scripts/cloud_build.py backend-runtime \
  --cache /workspace/cloud-build-cache/wheels \
  --docker-config /workspace/roadtrips-docker \
  --tag roadtrips-crud-api:local --revision local-crud-test
DOCKER_CONFIG=/workspace/roadtrips-docker DB_TEST_SKIP_BUILD=true \
  node tests/postgres/run.mjs
```

The explicit skip-build flag requires both prebuilt images and an API revision
label matching the runner's expected revision. A dirty checkout expects
`local-crud-test`; a clean checkout expects its full Git SHA. Rebuild both images
after any relevant source/schema changes. Matching labels identify the build but
are not proof of identical source content. Default runner behavior still builds
the committed Dockerfile. Disposable PostgreSQL schema initialization now streams
DDL through `psql` stdin after startup instead of mounting a checkout file; it
refuses a populated source volume before initialization. This avoids checkout
file permission dependence without changing host permissions. Report the offline container/CRUD result separately
from the blocked original Docker build-network gate.

For the schema-blocked preview smoke test, build both preview images with the
same revision and start them without another online build:

```sh
python scripts/cloud_build.py backend-runtime \
  --cache /workspace/cloud-build-cache/wheels \
  --docker-config /workspace/roadtrips-docker \
  --tag roadtrips-api-local:local-catalog-test --revision local-catalog-test
python scripts/cloud_build.py web \
  --cache /workspace/.npm-cache --docker-config /workspace/roadtrips-docker \
  --tag roadtrips-web-local:local-catalog-test --revision local-catalog-test
DOCKER_CONFIG=/workspace/roadtrips-docker ROADTRIPS_REVISION=local-catalog-test \
  docker compose up -d --no-build --wait
node --test tests/container-smoke.test.mjs
```

These are disposable local fixtures. They do not validate production credentials,
Neon deployment, real catalog coverage or live external routing providers.

## October 14 verification evidence

The offline backend test/runtime and frontend runtime images built successfully.
The running preview passed both `tests/container-smoke.test.mjs` tests. With
`DB_TEST_SKIP_BUILD=true`, `tests/postgres/run.mjs` passed real CRUD/ownership,
API restart, readiness loss/recovery, database recreation, backup/restore,
populated-target restore refusal and catalog activation-pointer restoration.
The disposable archive was 16,316 bytes; source and restore volumes were retained
and their containers stopped. This used synthetic data only.

Workspace logs: `/workspace/catalog-validation/cloud-smoke.log` and
`/workspace/catalog-validation/cloud-postgres-gate.log`; image build logs are
`cloud-offline-{test,runtime,web,preview-api}.log` in the same directory.
The original Dockerfile online dependency build remains blocked by nested DNS
and proxy certificate trust. Full backend/frontend source suites are separate
checks; these smoke/recovery results do not replace them.
