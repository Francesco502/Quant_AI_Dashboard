# AGENTS.md

Guidance for coding agents working in this repository.

## Project Overview

Quant-AI Dashboard is a **personal quantitative analysis and learning system**.
It is for research, paper trading, and strategy evaluation, not institutional production trading.

- Positioning: personal-use learning system
- Version: `2.2.0`
- Frontend: Next.js `16` on port `8686` (local dev)
- Backend: FastAPI on port `8685` (local dev)

## Core Goals

1. Personal portfolio analysis across stocks/funds/gold.
2. Market scanning for A-share/HK opportunities.
3. Paper trading for hypothesis validation.
4. Backtesting and strategy comparison.
5. Multi-user support with per-user configurations.
6. Daily-timeframe analysis only.
7. Deployable on 2-core/2GB hosts.
8. Learn from mature open-source patterns while keeping the scope pragmatic.

## Non-Negotiable Principles

1. Manual execution only.
2. No automatic real-money trading.
3. No minute/tick data requirements.
4. Personal learning priority over production complexity.

## Safety Guardrails

- Automatic trading is guarded by code:
  - `ALLOW_AUTO_TRADING=true` must be explicitly set.
  - `daemon_config.json` should keep trading disabled by default.
- Protected API routes require bearer authentication.

## Common Commands

### Backend
```bash
python -m uvicorn api.main:app --reload --port 8685
```

### Frontend
```bash
cd web
npm install
npm run dev
```

### Tests
```bash
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/e2e/ -m "e2e_inprocess" -v
```

### Quality
```bash
python -m compileall -q api core tests
cd web && npm run lint
cd web && npm run build
```

## Architecture

- `api/`: FastAPI routers and auth middleware
- `core/`: business logic (data, strategy, backtest, trading, monitoring)
- `web/src/app/`: App Router pages
- `web/src/components/`: reusable frontend components
- `tests/`: unit/integration/e2e and performance tests

## Key Routes

- Frontend pages:
  - `/portfolio-analysis`
  - `/market-scanner`
  - `/trading`
  - `/backtest`
  - `/agent-research`

- Backend API groups:
  - `/api/auth/*`
  - `/api/backtest/*`
  - `/api/trading/*`
  - `/api/portfolio/*`
  - `/api/user/*`
  - `/api/monitoring/*`
  - `/api/stz/*`

## Deployment Notes (2C/2G)

- Prefer `requirements.runtime.txt` for lean runtime images.
- Keep heavy ML stacks optional.
- Use `MARKET_SCAN_LOOKBACK_DAYS` to control scanning workload.
