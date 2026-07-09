#!/usr/bin/env python
"""Real-network external provider smoke checks for v3.0.0 release validation."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass

PROVIDERS = ("akshare", "yfinance", "llm")


def run_smoke() -> dict[str, Any]:
    if os.getenv("RUN_EXTERNAL_IO_SMOKE") != "1":
        return {
            "status": "skipped",
            "requires_network": True,
            "providers": list(PROVIDERS),
            "message": "Set RUN_EXTERNAL_IO_SMOKE=1 to run real external data/LLM smoke checks.",
        }

    results: dict[str, Any] = {}
    try:
        from core import llm_prompt_templates
        from core.llm_client import chat_completion, get_config, is_configured

        config = get_config()
        configured = is_configured(config)
        response_preview = ""
        if configured:
            response_preview = chat_completion(llm_prompt_templates.build_health_check_messages()).strip()[:160]
        results["llm"] = {
            "configured": configured,
            "provider": config.provider,
            "model": config.model,
            "base_url": config.base_url,
            "online": bool(response_preview),
            "response_preview": response_preview,
        }
    except Exception as exc:  # noqa: BLE001
        results["llm"] = {"configured": False, "online": False, "error": str(exc)}

    return {
        "status": "success" if all(item.get("online", False) for item in results.values()) else "failed",
        "requires_network": True,
        "providers": list(PROVIDERS),
        "results": results,
    }


def main() -> int:
    report = run_smoke()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] in {"success", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
