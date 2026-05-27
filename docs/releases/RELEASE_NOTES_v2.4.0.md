# Release Notes v2.4.0

Release date: 2026-05-26

## Safety And Access Control

- Added an explicit `ALLOW_AUTO_TRADING=true` runtime gate for automatic paper-trading scheduling and execution.
- Restricted system-level statistics and cleanup endpoints to administrators.
- Added authentication for WebSocket endpoints, including signal streaming.

## Portfolio And Market Data

- Allowed fractional portfolio shares for funds and other assets that do not trade in integer units.
- Improved market-review cache fallback so stale cached data can be used when live sources return an incomplete payload.
- Restored stale-data refresh for full-market strategy scans by default, with `MARKET_SCAN_REFRESH_STALE=false` available for local-cache-only runs.

## Release Hygiene

- Updated backend and frontend version markers to `2.4.0`.
- Added regression coverage for the release guardrails above.
