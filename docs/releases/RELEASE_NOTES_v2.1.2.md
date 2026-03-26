# Release Notes `v2.1.2`

## Highlights

- Upgraded release line from `v2.1.1` to `v2.1.2`.
- Fixed the optimized single-image Docker build path for real release packaging.
- Added CI validation for the optimized release image.
- Kept backend, frontend, docs, and smoke tests aligned to the new version line.

## Core Changes

- `Dockerfile.optimized` no longer depends on ignored local `daemon_config.json`.
- Frontend build can switch to static export during optimized image builds through `NEXT_STATIC_EXPORT=1`.
- CI now builds `Dockerfile.optimized` explicitly so release-image regressions fail before tagging.

## Operational Impact

- The documented release artifact (`Dockerfile.optimized`) is now buildable from a clean checkout.
- Single-image deployments remain same-origin and continue to expose frontend on `8686` and API on `8685`.
- Release verification now covers both source-level tests and image-level packaging.
