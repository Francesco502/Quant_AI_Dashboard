# Quant-AI Dashboard Release Notes

## Version
- `2.0.0-alpha.1`

## Release Date
- `2026-03-13`

## Release Type
- `Alpha`
- Internal pre-release for repository cleanup, validation, and release hardening.

## Summary
`v2.0.0-alpha.1` is the first pre-release for the upcoming `v2.0.0` line.
It includes major local feature integration work, but it is not yet a final public release.

## Intended Scope
This alpha currently focuses on these capability areas:

1. `LLM` 决策分析与每日分析流程
2. 市场复盘与 A 股数据增强
3. Agent 研究工具与结构化上下文
4. 系统监控、认证、限流与优化部署

## Current Validation Status
- Backend unit tests: passed
- Frontend lint: passed
- Integration, E2E, build, runtime smoke, and Docker validation are still part of the release gate

## Release Gate Before Beta
1. Clean the repository and remove non-release artifacts
2. Complete integration and E2E verification
3. Verify frontend build and runtime startup
4. Verify Docker and compose flow
5. Ensure GitHub Actions pass on the finalized branch

## Notes
- This pre-release replaces the earlier local-only `v2.0.0` wording
- Final `v2.0.0` must only be used after validation and tag creation
