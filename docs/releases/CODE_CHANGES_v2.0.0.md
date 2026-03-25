# Quant-AI Dashboard Code Changes (`v2.0.0`)

## Major Areas

### Data and Analysis
- Added Tushare-backed market context, trading calendar, and A-share metadata support
- Expanded daily analysis, market review, and agent research capabilities

### API and Backend
- Added new protected route groups for agent, market, monitoring, portfolio, scanner, external data, and user config workflows
- Improved auth middleware, RBAC, audit logging, caching, and monitoring integration

### Frontend
- Expanded dashboard pages for market review, scanner, portfolio analysis, backtest, system monitor, and agent research
- Refined API client and login behavior to align with protected backend flows

### Release Hardening
- Removed weak implicit admin bootstrap
- Removed real-looking secret defaults from code and examples
- Added focused tests for auth bootstrap and LLM configuration safety
- Promoted version metadata and runtime image tag references to `v2.0.0`
