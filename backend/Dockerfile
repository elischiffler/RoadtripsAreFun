# syntax=docker/dockerfile:1
FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS dependencies
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

FROM dependencies AS test
COPY backend/ ./
ENV PATH="/opt/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1
CMD ["pytest", "--cov=app", "--cov-report=term-missing", "--cov-fail-under=63"]

FROM dependencies AS runtime-dependencies
RUN /opt/venv/bin/pip uninstall -y pytest pytest-asyncio pytest-cov coverage

FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS runtime
ARG VCS_REF
RUN test -n "$VCS_REF" && groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
WORKDIR /app
COPY --from=runtime-dependencies /opt/venv /opt/venv
COPY backend/app ./app
ENV PATH="/opt/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
LABEL org.opencontainers.image.revision=$VCS_REF org.opencontainers.image.source="https://github.com/elischiffler/RoadtripsAreFun"
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "10"]
