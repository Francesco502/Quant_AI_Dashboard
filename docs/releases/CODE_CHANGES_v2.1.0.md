# Code Changes `v2.1.0`

## Core Themes

- Added personal-asset ledger, valuation, DCA rules, and daily sync.
- Reworked trading workspace into a unified simulation console.
- Added configurable automatic paper trading with strategy evaluation and full-market universe support.
- Hardened runtime security checks, LLM provider visibility, and monitoring.
- Unified frontend information architecture and the major page layout around the new workspace model.

## Backend Areas

- `api/routers/trading.py`, `api/routers/accounts.py`
- `api/routers/user_assets.py`
- `api/routers/stocktradebyz.py`
- `api/routers/llm_analysis.py`, `api/routers/agent.py`
- `core/user_assets.py`
- `core/auto_paper_trading.py`, `core/daemon.py`
- `core/trading_service.py`, `core/account_manager.py`, `core/order_manager.py`
- `core/data_service.py`, `core/tushare_provider.py`
- `core/llm_client.py`

## Frontend Areas

- `web/src/app/trading/page.tsx`
- `web/src/app/portfolio/page.tsx`
- `web/src/app/dashboard-llm/page.tsx`
- `web/src/app/page.tsx`
- `web/src/app/settings/page.tsx`
- `web/src/components/portfolio/*`
- `web/src/components/layout/*`
- `web/src/lib/api.ts`

## Release Hardening

- Runtime same-origin / CORS release checks.
- Full-market automatic trading defaults.
- Release docs, upgrade docs, rollback guide, and code-change manifest.
- Runtime image now includes optimizer dependencies required for non-degraded parameter search.
