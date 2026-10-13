# Milestone 1 — Build the demo application

By the end of this guide, you will have a small FastAPI service that runs locally and inside Docker, reports its version, and can deliberately fail its health check. You will also have automated tests for both healthy and unhealthy responses.

This covers **Milestone 1** in the [project guide](../DeployBox_Project_Guide.md). If you have not completed Milestone 0, check the tools in Step 1 first. Everything here runs locally; you do not need AWS yet.

The commands below use Bash on Linux, macOS, or WSL. Run them from the repository root unless a step says otherwise. Create the files shown using your editor.

## 1. Check your tools

```bash
python3 --version
git --version
docker --version
docker info
curl --version
```

Use Python 3.10 or newer. This guide uses Python 3.12 inside Docker. `docker info` should return server information without a connection or permission error. Start Docker Desktop or your Linux Docker service if the daemon is unavailable.

**Checkpoint:** Python and Docker are available, and Docker can communicate with its daemon.

## 2. Create the application directories

```bash
mkdir -p demo-app/tests
```

You will create this structure:

```text
demo-app/
├── app.py
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── .dockerignore
└── tests/
    └── test_app.py
```

The demo app lives separately from the deployment CLI you will build in Milestone 2.

## 3. Set up Python dependencies

Create `demo-app/requirements.txt`:

```text
fastapi
uvicorn
```

Create `demo-app/requirements-dev.txt`:

```text
-r requirements.txt
httpx
pytest
```

FastAPI defines the HTTP endpoints. Uvicorn serves the application. Pytest runs the tests, and HTTPX is required by FastAPI's test client. Separating development dependencies keeps test tools out of the runtime image.

Create a virtual environment in the repository root and install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r demo-app/requirements-dev.txt
```

Use `python -m ...` commands while the environment is active so that the interpreter and installed packages match. In a new terminal, activate it again with `source .venv/bin/activate`.

Add these entries to the root `.gitignore`, preserving any entries already there:

```gitignore
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
```

These initial dependency files do not pin versions. Record tested dependency versions before adding CI so later builds can use the same dependency set.

## 4. Write the application

Create `demo-app/app.py`:

```python
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse


app = FastAPI(title="DeployBox Demo")


@app.get("/")
def index():
    return {
        "service": "deploybox-demo",
        "version": os.getenv("APP_VERSION", "dev"),
    }


@app.get("/health")
def health():
    if os.getenv("FAIL_HEALTH", "0") == "1":
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy"},
        )
    return {"status": "healthy"}
```

`APP_VERSION` lets you identify the release without changing the code. `FAIL_HEALTH=1` simulates a service that starts but is not ready to receive traffic. Returning a JSON message alone is insufficient: the unhealthy response must have HTTP status **503** so DeployBox can detect it later.

## 5. Run the service without Docker

In your first terminal, with the virtual environment active:

```bash
cd demo-app
APP_VERSION=v1 python -m uvicorn app:app --host 127.0.0.1 --port 8080
```

`app:app` means “load the `app` object from `app.py`.” Leave this terminal running. Wait until Uvicorn reports that startup is complete.

In a second terminal:

```bash
curl http://localhost:8080/
curl -i http://localhost:8080/health
```

The first response should be:

```json
{"service":"deploybox-demo","version":"v1"}
```

The health response should have status `200 OK` and this body:

```json
{"status":"healthy"}
```

Stop Uvicorn with **Ctrl+C** in the first terminal, then restart it with the failure switch:

```bash
APP_VERSION=v2 FAIL_HEALTH=1 python -m uvicorn app:app --host 127.0.0.1 --port 8080
```

Repeat the health request from the second terminal. It should now return `503 Service Unavailable` with `{"status":"unhealthy"}`.

Stop Uvicorn again with **Ctrl+C**, then return the first terminal to the repository root:

```bash
cd ..
```

**Checkpoint:** You can change the reported version and health response using environment variables.

## 6. Add automated tests

Create `demo-app/tests/test_app.py`:

```python
from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def test_index_reports_configured_version(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "test-v1")

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "deploybox-demo",
        "version": "test-v1",
    }


def test_index_defaults_to_dev(monkeypatch):
    monkeypatch.delenv("APP_VERSION", raising=False)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["version"] == "dev"


def test_health_is_healthy_by_default(monkeypatch):
    monkeypatch.delenv("FAIL_HEALTH", raising=False)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_health_can_fail(monkeypatch):
    monkeypatch.setenv("FAIL_HEALTH", "1")

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy"}
```

Pytest's `monkeypatch` fixture temporarily changes environment variables and restores them after each test. This keeps tests independent of one another and of your terminal's environment.

Run the tests with the virtual environment active:

```bash
cd demo-app
python -m pytest -q
cd ..
```

Expected result: **4 passed**. TestClient exercises the app without starting Uvicorn or opening a network port.

## 7. Write the Dockerfile

Create `demo-app/Dockerfile`:

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home appuser
COPY --chown=appuser:appuser app.py .
USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

The image installs runtime dependencies and runs the service as a non-root user. Uvicorn binds to `0.0.0.0` **inside the container** so Docker can forward requests to it. `EXPOSE 8000` documents the port; you still need `docker run -p` to publish it.

Create `demo-app/.dockerignore`:

```text
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
tests/
requirements-dev.txt
```

## 8. Build and run a healthy container

From the repository root:

```bash
docker build -t deploybox-demo:v1 ./demo-app
docker run -d --name deploybox-demo \
  -p 127.0.0.1:8080:8000 \
  -e APP_VERSION=v1 \
  deploybox-demo:v1
```

The build context is `./demo-app`. Port `8080` on your machine forwards to port `8000` in the container, and the published port is limited to your local machine.

Check startup and then make the requests:

```bash
docker logs deploybox-demo
curl http://localhost:8080/
curl -i http://localhost:8080/health
```

If startup is still in progress, wait a moment and retry. Expect version `v1` and HTTP 200 from `/health`.

## 9. Simulate a failed release in Docker

Remove the healthy container and start a new one with the failure switch:

```bash
docker rm -f deploybox-demo
docker run -d --name deploybox-demo \
  -p 127.0.0.1:8080:8000 \
  -e APP_VERSION=v2 \
  -e FAIL_HEALTH=1 \
  deploybox-demo:v1
```

This reuses the same image with different runtime settings. `APP_VERSION=v2` changes the response label; it does not create a new image tag or change the image contents.

Once startup completes:

```bash
curl http://localhost:8080/
curl -i http://localhost:8080/health
```

Expect version `v2` and HTTP **503**. The container will still be running: a running process can serve an unhealthy application. That distinction is why DeployBox needs HTTP health checks.

Ordinary `curl -i` prints an HTTP error response but does not treat it as a failed command. To check the exit behavior a deployment script would need:

```bash
curl --fail http://localhost:8080/health
echo $?
```

For HTTP 503, expect a nonzero exit code, typically `22`.

This step manually replaces the container. Automatic rejection and rollback belong to Milestone 2.

## 10. Restore the healthy container and clean up

```bash
docker rm -f deploybox-demo
docker run -d --name deploybox-demo \
  -p 127.0.0.1:8080:8000 \
  -e APP_VERSION=v1 \
  deploybox-demo:v1
```

After startup, verify that `/health` returns HTTP 200 again. When you finish practicing, remove the container:

```bash
docker rm -f deploybox-demo
```

The image remains available for Milestone 2. You can exit the Python virtual environment with `deactivate`.

## 11. Review and commit your work

From the repository root:

```bash
git status --short
git diff --check
git add demo-app/ .gitignore
git diff --cached
git commit -m "Add demo app with health checks and Docker support"
```

Review the staged diff before committing. Confirm that the virtual environment and Python caches are excluded.

## Completion checklist

- [ ] `/` returns the service name and the configured version.
- [ ] `/health` returns HTTP 200 by default.
- [ ] `FAIL_HEALTH=1` makes `/health` return HTTP 503.
- [ ] All four automated tests pass.
- [ ] The Docker image builds successfully.
- [ ] The app runs on container port 8000 through local port 8080.
- [ ] Healthy and unhealthy responses have both been checked inside Docker.
- [ ] Your application files are committed without generated files.

Once these checks pass, move to **Milestone 2: build the DeployBox CLI**.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `No module named fastapi`, `httpx`, or `pytest` | Activate `.venv` and install `demo-app/requirements-dev.txt`. |
| `No module named app` when testing | Run `python -m pytest -q` from inside `demo-app`. |
| Virtual environment creation fails on Debian/Ubuntu | Install the distribution's `python3-venv` package, then retry Step 3. |
| Docker cannot connect to its daemon | Start Docker and verify that `docker info` works. |
| Port 8080 is already in use | Stop the earlier Uvicorn process or container, or publish `127.0.0.1:8081:8000` and use port 8081 in curl. |
| Container name is already in use | Inspect `docker ps -a`; remove the earlier tutorial container before reusing its name. |
| Curl cannot connect | Check `docker ps -a` and `docker logs deploybox-demo`; confirm the app has finished starting. |
| Health stays at 200 | Recreate the container with `-e FAIL_HEALTH=1`. An existing container does not inherit later changes in your terminal. |

## Official references

- [FastAPI first steps](https://fastapi.tiangolo.com/tutorial/first-steps/)
- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [FastAPI in Docker](https://fastapi.tiangolo.com/deployment/docker/)
