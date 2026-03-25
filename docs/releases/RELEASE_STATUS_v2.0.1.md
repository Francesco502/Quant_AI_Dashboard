# Release Status (`v2.0.1`)

## Current Position
- Release line: `v2.0.1`
- Status: `release-candidate validation in progress`

## Completed In This Cycle
- Fixed take-profit trigger construction for long positions.
- Fixed market-order risk fallback so explicit invalid negative prices are still rejected.
- Added release-oriented runtime security validation and health reporting.
- Added LLM provider availability status plus `GET /api/llm-analysis/health-check`.
- Added real benchmark series loading for `/api/backtest/extended-analysis`.
- Added Twilio-based SMS alert delivery support.
- Updated API, frontend, test, and release-facing docs to point at `v2.0.1`.

## Required Evidence Before Tagging
1. Unit, integration, smoke, and frontend build validation must be green.
2. External release validation must run against live frontend/backend services.
3. Production deployment must either set `CORS_ORIGINS` or `API_EXPECT_SAME_ORIGIN=1`.
4. Production deployment must use a non-default `SECRET_KEY`.
