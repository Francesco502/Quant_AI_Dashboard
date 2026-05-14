"""Background daemon for scheduled maintenance tasks.

Responsibilities:
- Keep local market data up to date.
- Run scheduled model training.
- Run daily analysis tasks.
- Persist latest runtime status for dashboard visibility.

Local run example:
    cd Quant_AI_Dashboard
    python -m core.daemon
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

from .data_updater import update_local_history_for_tickers
from .scheduler import (
    setup_data_update_job,
    setup_trading_job,
    setup_training_job,
    setup_daily_analysis_job,
    run_forever,
)
from .training_pipeline import TrainingPipeline
from .feature_store import get_feature_store
from .data_store import load_local_price_history
from .auto_paper_trading import run_auto_trading_cycle
from .time_utils import local_now_str


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "daemon_config.json")
STATUS_PATH = os.path.join(BASE_DIR, "daemon_status.json")

LEGACY_RELEASE_TRADING_CONFIG = {
    "account_name": "Auto Paper Trading",
    "strategy_ids": ["ema_crossover"],
    "universe_mode": "manual",
    "universe": ["510500", "159915"],
    "universe_limit": 0,
    "max_positions": 3,
    "evaluation_days": 180,
    "min_total_return": 0.03,
    "min_sharpe_ratio": 0.3,
    "max_drawdown": 0.2,
    "top_n_strategies": 3,
}


def _default_config() -> Dict[str, Any]:
    return {
        "universe": ["013281", "002611", "160615", "016858", "159755", "006810"],
        "days": 365,
        "data_sources": ["AkShare", "Tushare"],
        "alpha_vantage_key": "",
        "tushare_token": "",
        "data_update": {
            "enabled": True,
            "interval_minutes": 120,
        },
        "trading": {
            "enabled": False,
            "interval_minutes": 60,
            "max_positions": 3,
            "initial_capital": 100_000.0,
            "username": "admin",
            "account_name": "全市场自动模拟交易",
            "strategy_ids": [
                "sma_crossover",
                "ema_crossover",
                "mean_reversion",
                "rsi_reversion",
                "macd_trend",
                "breakout_momentum",
                "donchian_breakout",
                "momentum_rotation",
            ],
            "evaluation_days": 180,
            "min_total_return": 0.0,
            "min_sharpe_ratio": 0.0,
            "max_drawdown": 0.35,
            "top_n_strategies": 3,
            "universe_mode": "cn_a_share",
            "universe": [],
            "universe_limit": 0,
            "evaluation_limit": 120,
        },
        "training": {
            "enabled": False,
            "time": "02:00",
            "model_type": "xgboost",
            "auto_promote": True,
            "generate_signals": True,
            "min_train_days": 60,
            "retrain_interval_days": 7,
            "min_improvement_threshold": 0.02,
        },
        "features": {
            "use_enhanced": True,
        },
        "daily_analysis": {
            "enabled": False,
            "time": "18:00",
        },
    }


def _matches_legacy_release_trading_config(trading_cfg: Dict[str, Any]) -> bool:
    return all(trading_cfg.get(key) == value for key, value in LEGACY_RELEASE_TRADING_CONFIG.items())


def _normalize_config(config: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
    default = _default_config()
    normalized = dict(config or {})
    changed = False

    for key, value in default.items():
        if key not in normalized:
            normalized[key] = value
            changed = True

    trading_cfg = dict(normalized.get("trading", {}) or {})
    default_trading = dict(default["trading"])

    for key, value in default_trading.items():
        if key not in trading_cfg:
            trading_cfg[key] = value
            changed = True

    if _matches_legacy_release_trading_config(trading_cfg):
        trading_cfg = dict(default_trading)
        changed = True

    normalized["trading"] = trading_cfg
    return normalized, changed
# ACCOUNT_PATH is deprecated; account state now lives in SQLite.

def _ensure_dirs() -> None:
    os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)


def _load_config_legacy() -> Dict[str, Any]:
    """Deprecated legacy config loader kept only for historical reference."""
    if not os.path.exists(CONFIG_PATH):
        default = {
            "universe": ["013281", "002611", "160615", "016858", "159755", "006810"],
            "days": 365,
            "data_sources": ["AkShare", "Tushare"],
            "alpha_vantage_key": "",
            "tushare_token": "",
            "data_update": {
                "enabled": True,
                "interval_minutes": 120,  # Low-spec optimization: update every 2 hours.
            },
            "trading": {
                "enabled": False,
                "interval_minutes": 60,
                "max_positions": 5,
                "initial_capital": 100_000.0,
                "username": "admin",
                "account_name": "全市场自动模拟交易",
                "strategy_ids": [
                    "sma_crossover",
                    "ema_crossover",
                    "mean_reversion",
                    "rsi_reversion",
                    "macd_trend",
                    "breakout_momentum",
                    "donchian_breakout",
                    "momentum_rotation",
                ],
                "evaluation_days": 180,
                "min_total_return": 0.0,
                "min_sharpe_ratio": 0.0,
                "max_drawdown": 0.35,
                "top_n_strategies": 3,
                "universe_mode": "cn_a_share",
                "universe": [],
                "universe_limit": 0,
                "evaluation_limit": 120,
            },
            "training": {
                "enabled": False,
                "time": "02:00",  # Low-spec optimization: run during off-peak hours.
                "model_type": "xgboost",  # Supported: xgboost, lightgbm, random_forest. Avoid lstm/gru on low-spec hosts.
                "auto_promote": True,
                "generate_signals": True,
                "min_train_days": 60,
                "retrain_interval_days": 7,
                "min_improvement_threshold": 0.02,
            },
            "features": {
                "use_enhanced": True,
            },
            "daily_analysis": {
                "enabled": False,
                "time": "18:00",
            },
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        return default

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config() -> Dict[str, Any]:
    """Load daemon configuration with release-default normalization."""
    if not os.path.exists(CONFIG_PATH):
        default = _default_config()
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        return default

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    normalized, changed = _normalize_config(loaded)
    if changed:
        save_config(normalized)
    return normalized


def save_config(config: Dict[str, Any]) -> None:
    """Persist daemon configuration to disk."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def _is_pid_running(pid: Any) -> bool:
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return False

    if pid_int <= 0:
        return False

    try:
        import psutil

        return bool(psutil.pid_exists(pid_int))
    except Exception:
        pass

    if os.name == "nt":
        try:
            import subprocess

            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid_int}"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return str(pid_int) in result.stdout
        except Exception:
            return False

    try:
        os.kill(pid_int, 0)
        return True
    except OSError:
        return False


def load_status() -> Dict[str, Any]:
    """Read daemon runtime status from disk."""
    if not os.path.exists(STATUS_PATH):
        return {}

    try:
        with open(STATUS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        if data.get("daemon_running") and not _is_pid_running(data.get("daemon_pid")):
            data = dict(data)
            data["daemon_running"] = False
        return data
    except Exception:
        return {}


def save_status(patch: Dict[str, Any]) -> None:
    """Write daemon runtime status with incremental patch updates."""
    status = load_status()

    status.update(patch)
    status["last_updated_at"] = local_now_str()
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def _load_account() -> Dict[str, Any]:
    """Load the daemon paper account from SQLite, creating one on first run."""
    from .database import get_database
    from .account_manager import AccountManager

    try:
        db = get_database()
        account_mgr = AccountManager(db)

        # Fetch the first active account for the default daemon user (user_id=1).
        cursor = db.conn.cursor()
        cursor.execute(
            """
            SELECT id, account_name, balance, frozen, initial_capital
            FROM accounts
            WHERE user_id = 1 AND status = 'active'
            ORDER BY id ASC
            LIMIT 1
            """
        )
        row = cursor.fetchone()

        if not row:
            account_id = account_mgr.create_account(
                user_id=1,
                name="Daemon Auto Paper Trading",
                initial_balance=1_000_000.0,
            )
            return {
                "account_id": account_id,
                "initial_capital": 1_000_000.0,
                "cash": 1_000_000.0,
                "positions": {},
                "equity_history": [],
                "trade_log": [],
            }

        account_id = row["id"]
        cursor.execute(
            """
            SELECT ticker, shares FROM positions WHERE account_id = ?
            """,
            (account_id,),
        )
        positions = {r["ticker"]: r["shares"] for r in cursor.fetchall()}

        return {
            "account_id": account_id,
            "initial_capital": row["initial_capital"],
            "cash": row["balance"],
            "positions": positions,
            "equity_history": [],
            "trade_log": [],
        }

    except Exception as e:
        logging.error("daemon: failed to load daemon account: %s", e)
        return {
            "initial_capital": 1_000_000.0,
            "cash": 1_000_000.0,
            "positions": {},
            "equity_history": [],
            "trade_log": [],
        }


def _save_account(account: Dict[str, Any]) -> None:
    """Account state is persisted in SQLite; this stub remains for compatibility."""
    pass


def data_update_job(cfg: Dict[str, Any]) -> None:
    """Run scheduled historical data updates and feature refresh."""
    if not _memory_guard():
        return
    universe: List[str] = cfg.get("universe") or []
    if not universe:
        logging.warning("daemon: universe is empty, skipping data update job.")
        return

    days = int(cfg.get("days", 365))
    data_sources = cfg.get("data_sources") or ["AkShare"]
    alpha_vantage_key = os.getenv("ALPHA_VANTAGE_KEY") or cfg.get("alpha_vantage_key") or ""
    tushare_token = os.getenv("TUSHARE_TOKEN") or cfg.get("tushare_token") or ""

    logging.info("daemon: starting data update job, tickers=%d, days=%d", len(universe), days)
    update_local_history_for_tickers(
        tickers=universe,
        days=days,
        data_sources=data_sources,
        alpha_vantage_key=alpha_vantage_key,
        tushare_token=tushare_token,
    )
    logging.info("daemon: data update job completed.")

    logging.info("daemon: refreshing feature store after data update...")
    feature_store = get_feature_store()
    use_enhanced_features = cfg.get("features", {}).get("use_enhanced", True)
    feature_success_count = 0
    feature_fail_count = 0

    for ticker in universe:
        try:
            price_series = load_local_price_history(ticker)
            if price_series is not None and not price_series.empty:
                if feature_store.update_features_for_ticker(
                    ticker, price_series, use_enhanced_features=use_enhanced_features
                ):
                    feature_success_count += 1
                else:
                    feature_fail_count += 1
        except Exception as e:
            logging.warning("daemon: failed to refresh features for %s: %s", ticker, e)
            feature_fail_count += 1

    logging.info(
        "daemon: feature refresh finished, success=%d, failed=%d",
        feature_success_count,
        feature_fail_count,
    )
    save_status(
        {
            "last_data_update": local_now_str(),
            "last_feature_update": local_now_str(),
            "feature_success_count": feature_success_count,
            "feature_fail_count": feature_fail_count,
        }
    )


def _memory_guard(threshold_percent: int = 80) -> bool:
    """Memory guard: skip heavy jobs when system memory usage is above threshold."""
    try:
        import gc
        import time
        import psutil

        mem = psutil.virtual_memory()
        if mem.percent > threshold_percent:
            logging.warning(
                "daemon: memory usage %.1f%% is above threshold %.1f%%, skipping heavy job",
                mem.percent,
                threshold_percent,
            )
            gc.collect()
            time.sleep(30)
            return False
    except Exception as e:
        logging.debug("daemon: memory_guard check failed: %s", e)
    return True


def daily_analysis_job(cfg: Dict[str, Any]) -> None:
    """Run the scheduled daily LLM analysis task."""
    if not _memory_guard():
        return
    try:
        from core.daily_analysis import run_daily_analysis_from_env

        logging.info("daemon: starting daily analysis job...")
        result = run_daily_analysis_from_env(include_market_review=True)
        save_status(
            {
                "last_daily_analysis": local_now_str(),
                "last_daily_analysis_result": {
                    "result_count": len(result.get("results", [])),
                    "has_market_review": bool(result.get("market_review")),
                },
            }
        )
        logging.info("daemon: daily analysis job completed.")
    except Exception as e:
        logging.warning("daemon: daily analysis job failed: %s", e)


def training_job(cfg: Dict[str, Any]) -> None:
    """Run scheduled model training and prediction generation."""
    if not _memory_guard():
        return
    universe: List[str] = cfg.get("universe") or []
    if not universe:
        logging.warning("daemon: universe is empty, skipping training job.")
        return

    training_config = cfg.get("training", {})
    model_type = training_config.get("model_type", "xgboost")
    if model_type in ("lstm", "gru") and os.environ.get("DISABLE_HEAVY_MODELS", "").strip().lower() in ("1", "true", "yes"):
        logging.info("daemon: DISABLE_HEAVY_MODELS is enabled, fallback %s -> xgboost", model_type)
        model_type = "xgboost"
    auto_promote = training_config.get("auto_promote", True)
    generate_signals = training_config.get("generate_signals", True)

    logging.info(
        "daemon: starting training job, tickers=%d, model_type=%s",
        len(universe),
        model_type,
    )

    try:
        pipeline = TrainingPipeline(
            model_dir=os.path.join(BASE_DIR, "models"),
            min_train_days=training_config.get("min_train_days", 60),
            retrain_interval_days=training_config.get("retrain_interval_days", 7),
            min_improvement_threshold=training_config.get("min_improvement_threshold", 0.02),
        )

        stats = pipeline.run_training_job(
            tickers=universe,
            model_type=model_type,
            auto_promote=auto_promote,
            generate_signals=generate_signals,
        )

        logging.info(
            "daemon: training finished, total=%d, trained=%d, promoted=%d, failed=%d, skipped=%d",
            stats["total"],
            stats["trained"],
            stats["promoted"],
            stats["failed"],
            stats["skipped"],
        )

        save_status(
            {
                "last_training_run": local_now_str(),
                "training_stats": {
                    "total": stats["total"],
                    "trained": stats["trained"],
                    "promoted": stats["promoted"],
                    "failed": stats["failed"],
                    "skipped": stats["skipped"],
                },
            }
        )

    except Exception as e:
        logging.error("daemon: training job failed: %s", e, exc_info=True)
        save_status(
            {
                "last_training_run": local_now_str(),
                "training_error": str(e),
            }
        )


def trading_job(cfg: Dict[str, Any]) -> None:
    """Run a single paper-trading rebalance task."""
    if not _memory_guard():
        return

    try:
        from api.routers.trading import get_trading_service

        result = run_auto_trading_cycle(cfg, get_trading_service())
        save_status(
            {
                "trading_run_state": "idle",
                "last_trading_run": local_now_str(),
                "last_trading_result": result,
                "last_trading_error": None,
            }
        )
        logging.info(
            "daemon: auto trading completed, validated=%d, orders=%d",
            len(result.get("validated_strategies", [])),
            len(result.get("executed_orders", [])),
        )
    except Exception as e:
        logging.error("daemon: auto trading failed: %s", e, exc_info=True)
        save_status(
            {
                "last_trading_run": local_now_str(),
                "last_trading_error": str(e),
            }
        )


def main() -> None:
    _ensure_dirs()

    # Write PID file for process management.
    pid_file = os.path.join(BASE_DIR, "logs", "daemon.pid")
    current_pid = os.getpid()

    # Detect existing pid file and print warning if a process is still running.
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r", encoding="utf-8") as f:
                old_pid = int(f.read().strip())
            import platform
            if platform.system() == "Windows":
                try:
                    import subprocess
                    result = subprocess.run(
                        ["tasklist", "/FI", f"PID eq {old_pid}"],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if str(old_pid) in result.stdout:
                        logger.warning("Existing daemon process detected (PID=%s).", old_pid)
                        logger.warning("Current process PID=%s, pid file will be overwritten.", current_pid)
                except Exception:
                    pass
            else:
                try:
                    os.kill(old_pid, 0)
                    logger.warning("Existing daemon process detected (PID=%s).", old_pid)
                    logger.warning("Current process PID=%s, pid file will be overwritten.", current_pid)
                except OSError:
                    pass
        except (ValueError, FileNotFoundError):
            pass

    # Write current process pid.
    try:
        with open(pid_file, "w", encoding="utf-8") as f:
            f.write(str(current_pid))
    except Exception as e:
        logger.warning("Failed to write pid file %s: %s", pid_file, e)

    logging.basicConfig(
        filename=os.path.join(BASE_DIR, "logs", "daemon.log"),
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    cfg = load_config()
    logging.info("daemon: configuration loaded.")
    logging.info("daemon: process PID = %s", os.getpid())
    save_status(
        {
            "daemon_running": True,
            "daemon_pid": os.getpid(),
            "last_started_at": local_now_str(),
            "config_trading_enabled": bool(cfg.get("trading", {}).get("enabled", False)),
            "config_trading_interval_minutes": int(cfg.get("trading", {}).get("interval_minutes", 0) or 0),
        }
    )

    # Register scheduled jobs.
    setup_data_update_job(cfg.get("data_update", {}), lambda: data_update_job(cfg))
    setup_trading_job(cfg.get("trading", {}), lambda: trading_job(cfg))
    setup_training_job(cfg.get("training", {}), lambda: training_job(cfg))
    setup_daily_analysis_job(cfg.get("daily_analysis", {}), lambda: daily_analysis_job(cfg))

    # Register daily settlement task (15:30 local time) — configurable.
    settlement_enabled = bool(cfg.get("settlement", {}).get("enabled", True))
    asset_sync_enabled = bool(cfg.get("asset_sync", {}).get("enabled", True))

    try:
        import schedule

        if settlement_enabled:
            def _daily_settlement_job():
                """Run settlement for all accounts."""
                try:
                    from .paper_account import PaperAccount
                    from .database import Database

                    db = Database()
                    cursor = db.conn.cursor()
                    cursor.execute("SELECT id, user_id FROM accounts")
                    accounts = cursor.fetchall()
                    for acc in accounts:
                        try:
                            pa = PaperAccount(user_id=acc["user_id"], account_id=acc["id"], db=db)
                            result = pa.daily_settlement()
                            logging.info(
                                "daemon: settlement completed for account %s, equity=%.2f",
                                acc["id"],
                                result["equity"],
                            )
                        except Exception as e:
                            logging.error("daemon: settlement failed for account %s: %s", acc["id"], e)
                except Exception as e:
                    logging.error("daemon: daily settlement job error: %s", e)

            schedule.every().day.at("15:30").do(_daily_settlement_job)
            logging.info("daemon: registered daily settlement job at 15:30")
        else:
            logging.info("daemon: daily settlement job disabled (settlement.enabled=false)")

        if asset_sync_enabled:
            def _daily_user_asset_sync_job():
                """Run personal asset DCA reconciliation and snapshot sync."""
                try:
                    from .user_assets import get_user_asset_service

                    result = get_user_asset_service().run_daily_sync_for_all_users()
                    logging.info(
                        "daemon: user asset sync completed, users=%s",
                        result.get("users_synced", 0),
                    )
                except Exception as e:
                    logging.error("daemon: daily user asset sync job error: %s", e)

            schedule.every().day.at("18:10").do(_daily_user_asset_sync_job)
            logging.info("daemon: registered daily user asset sync job at 18:10")
        else:
            logging.info("daemon: daily user asset sync job disabled (asset_sync.enabled=false)")
    except Exception as e:
        logging.warning("daemon: failed to register daily jobs: %s", e)

    logging.info("daemon: scheduler loop started.")

    try:
        run_forever()
    except KeyboardInterrupt:
        logging.info("daemon: interrupt received, shutting down.")
    finally:
        save_status(
            {
                "daemon_running": False,
                "last_stopped_at": local_now_str(),
            }
        )
        # Cleanup pid file.
        try:
            if os.path.exists(pid_file):
                os.remove(pid_file)
        except Exception:
            pass


if __name__ == "__main__":
    main()
