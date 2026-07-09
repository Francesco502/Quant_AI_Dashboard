# Release Guide

## Goal

Use this guide to turn the current worktree into a releasable `v3.0.0` candidate with a reproducible validation record.

## 1. Freeze Scope

Before tagging or publishing:

- decide which files belong to the release
- remove or archive unrelated local experiments
- keep generated output out of source control

Generated artifacts that should not be committed:

- `output/`
- `.playwright-cli/`
- `.opencode/`
- `tmp/`
- coverage output
- local logs

## 2. Validate The Candidate

Run the standard gates in this order:

```powershell
python -m compileall -q api core tests
python -m pytest tests/unit -q
python -m pytest tests/integration -q
python -m pytest tests/test_v3_smoke.py -q
python -m pytest tests/e2e -m "e2e_inprocess" -q
python scripts/deployment_readiness_check.py --strict

cd web
npm audit --audit-level=low
npm run lint
npm run build
NEXT_PUBLIC_API_URL=/api NEXT_STATIC_EXPORT=1 NEXT_TELEMETRY_DISABLED=1 NODE_ENV=production npx next build
cd ..

python -m playwright install chromium
python scripts/release_check.py
RUN_EXTERNAL_IO_SMOKE=1 python scripts/external_io_smoke.py
```

The release report is written to:

```text
output/reports/release_check_report.txt
```

## 3. Validate The Release Image

```powershell
docker build -f Dockerfile.optimized -t quant-ai-dashboard:3.0.0 .
docker build -f Dockerfile.optimized --build-arg INSTALL_NATIVE_KERNEL=true -t quant-ai-dashboard:3.0.0-native .
```

For compose-based verification:

```powershell
docker compose up -d --build
docker compose -f docker-compose.worker.yml --profile scan --profile backtest up -d --build
docker compose logs -f
```

Then verify:

- `http://localhost:8686/login`
- `http://localhost:8686/`
- `http://localhost:8685/api/health`

## 4. Update Release Records

Before tagging:

- update versioned release docs under `docs/releases/` when the scope is final
- make sure README, deployment docs, and upgrade guidance match the actual startup and validation flow
- keep CI release validation aligned with `scripts/release_check.py`

## 5. Release Sign-Off Checklist

Release is ready only when all of the following are true:

- worktree scope is intentional
- compile, unit, integration, smoke, in-process E2E, frontend build, static-export build, and external release validation all pass
- Docker optimized image builds successfully
- worker compose profiles validate and required worker heartbeats are online when scan/backtest task flow is enabled
- LLM health check is online against the release provider; v3.0.0 defaults to DeepSeek-compatible `deepseek-v4-flash`
- login, dashboard, portfolio, trading, backtest, and research pages render against the target backend
- rollback instructions and deployment environment are known
