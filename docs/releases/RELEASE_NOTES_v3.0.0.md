# Release Notes v3.0.0

Release date: 2026-07-09

## Summary

v3.0.0 focuses on release-grade performance and deployment readiness for a personal quantitative research workflow on small 2-core/2GB hosts.

## Highlights

- Added persisted task flow for large backtests and market scans.
- Added worker profiles for prediction, market refresh, scan, and backtest workloads.
- Added precomputed-signal fast path for array-friendly backtests.
- Added feature snapshot storage and hot-cache market scanning.
- Defaulted LLM support to DeepSeek-compatible OpenAI API settings with built-in v3 prompt templates.
- Added optional Rust native scoring kernel behind `INSTALL_NATIVE_KERNEL=true`; Python fallback remains the default.
- Added release checks for Playwright browser availability, deployment readiness, worker heartbeat status, and performance gates.

## Release Requirements

- LLM must be online for the v3.0.0 release target. Configure `DEEPSEEK_API_KEY` or `DS_API_KEY`; default model is `deepseek-v4-flash`.
- For full market scan and large backtest workloads, run `scan-worker` and `backtest-worker`, and build feature snapshots on schedule.
- Run `scripts/deployment_readiness_check.py --strict` in the target deployment environment before release.
- Run `RUN_EXTERNAL_IO_SMOKE=1 python scripts/external_io_smoke.py` with real network/API access before release.
- If Docker images must include Rust native acceleration, build with `INSTALL_NATIVE_KERNEL=true`; otherwise Python fallback is expected.
