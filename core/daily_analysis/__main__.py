from __future__ import annotations

from . import run_daily_analysis_from_env


def main() -> None:
    run_daily_analysis_from_env(include_market_review=True, send_push=True)


if __name__ == "__main__":
    main()

