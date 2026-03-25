# Quant-AI Dashboard Release Notes

## Version
- `2.0.0`

## Release Date
- `2026-03-13`

## Release Type
- `General Availability target`
- This document tracks the formal release contents for the `2.0.0` line while final validation is being completed.

## Summary
`v2.0.0` promotes the current dashboard to a formal major release focused on personal quantitative research, paper trading, backtesting, market review, and agent-assisted analysis.

This line includes:

1. Tushare-enhanced A-share market context and trading calendar support
2. Daily analysis and market review improvements
3. Agent tools with structured trading context
4. Hardened API auth, monitoring, caching, and deployment paths
5. Frontend updates across market, trading, backtest, portfolio, and agent research pages

## Notable Hardening Changes

- Removed real-looking example secrets from release-facing configuration
- Replaced implicit weak default admin bootstrap with explicit credential-based bootstrap
- External release validation now requires explicitly configured test credentials
- LLM client now falls back to a dummy provider when no API key is configured

## Release Gate

Before the final public tag is created, the following must be green and documented:

1. Backend compile and test matrix
2. Frontend lint and production build
3. Docker build and runtime health
4. External release smoke validation
5. GitHub-side release evidence
