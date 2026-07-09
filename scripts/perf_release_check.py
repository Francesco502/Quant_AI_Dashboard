#!/usr/bin/env python
"""Generate v3.0.0 performance-release evidence."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from core import performance_targets


REPORT_PATH = Path("output/reports/perf_release_check.md")


def build_report(output_path: str | Path | None = None, *, rss_mb: float | None = None) -> str:
    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rss_mb": rss_mb,
        "targets": performance_targets.as_dict(),
    }
    report = "\n".join(
        [
            "# v3.0.0 Performance Release Check",
            "",
            "## API-only RSS Snapshot",
            "",
            f"- rss_mb: {snapshot['rss_mb']}",
            f"- API_ONLY_RSS_MAX_MB: {snapshot['targets']['API_ONLY_RSS_MAX_MB']}",
            "",
            "## Targets",
            "",
            "```json",
            json.dumps(snapshot["targets"], ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report, encoding="utf-8")
    return report


def main() -> int:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(build_report(), encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
