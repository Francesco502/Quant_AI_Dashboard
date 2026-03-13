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

from .data_updater import update_local_history_for_tickers
from .scheduler import (
    setup_data_update_job,
    setup_training_job,
    setup_daily_analysis_job,
    run_forever,
)
from .training_pipeline import TrainingPipeline
from .feature_store import get_feature_store
from .data_store import load_local_price_history


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "daemon_config.json")
STATUS_PATH = os.path.join(BASE_DIR, "daemon_status.json")
# ACCOUNT_PATH 宸插純鐢紝鐜板湪浣跨敤鏁版嵁搴撳瓨鍌?

def _ensure_dirs() -> None:
    os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)


def load_config() -> Dict[str, Any]:
    """Load daemon configuration; create defaults when config file is missing."""
    if not os.path.exists(CONFIG_PATH):
        default = {
            "universe": ["013281", "002611", "160615", "016858", "159755", "006810"],
            "days": 365,
            "data_sources": ["AkShare", "Tushare"],
            "alpha_vantage_key": "",
            "tushare_token": "",
            "data_update": {
                "enabled": True,
                "interval_minutes": 120,  # 浣庨厤浼樺寲锛氭瘡2灏忔椂鏇存柊
            },
            "trading": {
                "enabled": False,
                "interval_minutes": 60,
                "max_positions": 5,
                "initial_capital": 1_000_000.0,
            },
            "training": {
                "enabled": True,
                "time": "02:00",  # 浣庨厤浼樺寲锛氬噷鏅ㄤ綆宄版墽琛?                "model_type": "xgboost",  # 鍙€? "xgboost", "lightgbm", "random_forest"锛堜綆閰嶇鐢?lstm/gru锛?                "auto_promote": True,
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


def save_status(patch: Dict[str, Any]) -> None:
    """Write daemon runtime status with incremental patch updates."""
    status: Dict[str, Any]
    if os.path.exists(STATUS_PATH):
        try:
            with open(STATUS_PATH, "r", encoding="utf-8") as f:
                status = json.load(f)
        except Exception:
            status = {}
    else:
        status = {}

    status.update(patch)
    status["last_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def _load_account() -> Dict[str, Any]:
    """浠庢暟鎹簱鍔犺浇妯℃嫙璐︽埛锛堝畧鎶よ繘绋嬬増鏈級"""
    from .database import get_database
    from .account_manager import AccountManager

    try:
        db = get_database()
        account_mgr = AccountManager(db)

        # 鑾峰彇榛樿鐢ㄦ埛锛坉aemon浣跨敤鐢ㄦ埛ID=1锛夌殑绗竴涓椿璺冭处鎴?        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT id, account_name, balance, frozen, initial_capital
            FROM accounts
            WHERE user_id = 1 AND status = 'active'
            ORDER BY id ASC
            LIMIT 1
        """)
        row = cursor.fetchone()

        if not row:
            # 鍒涘缓榛樿璐︽埛
            account_id = account_mgr.create_account(
                user_id=1,
                name="Daemon妯℃嫙璐︽埛",
                initial_balance=1_000_000.0
            )
            account = account_mgr.get_account(account_id, user_id=1)
            return {
                "account_id": account_id,
                "initial_capital": 1_000_000.0,
                "cash": 1_000_000.0,
                "positions": {},
                "equity_history": [],
                "trade_log": [],
            }

        account_id = row["id"]

        # 鑾峰彇鎸佷粨
        cursor.execute("""
            SELECT ticker, shares FROM positions WHERE account_id = ?
        """, (account_id,))
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
        logging.error("daemon: 鍔犺浇璐︽埛澶辫触: %s", e)
        # 杩斿洖榛樿缁撴瀯
        return {
            "initial_capital": 1_000_000.0,
            "cash": 1_000_000.0,
            "positions": {},
            "equity_history": [],
            "trade_log": [],
        }


def _save_account(account: Dict[str, Any]) -> None:
    """淇濆瓨璐︽埛鍒版暟鎹簱锛堝畧鎶よ繘绋嬬増鏈級

    娉ㄦ剰锛氱幇鍦ㄦ暟鎹疄鏃跺啓鍏ユ暟鎹簱锛屾鍑芥暟淇濈暀鐢ㄤ簬鍏煎
    """
    # 鏁版嵁宸插疄鏃跺啓鍏ユ暟鎹簱锛屾棤闇€棰濆鎿嶄綔
    pass


def data_update_job(cfg: Dict[str, Any]) -> None:
    """鏁版嵁鏇存柊浠诲姟锛氳皟鐢?data_updater 涓?universe 鍒楄〃澧為噺鏇存柊鏈湴浠撳簱锛屽苟璁＄畻鐗瑰緛"""
    if not _memory_guard():
        return
    universe: List[str] = cfg.get("universe") or []
    if not universe:
        logging.warning("daemon: universe is empty, skipping data update job.")
        return

    days = int(cfg.get("days", 365))
    data_sources = cfg.get("data_sources") or ["AkShare"]
    # Prefer env vars over config file for secrets.
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

    # 闃舵涓€锛氭暟鎹洿鏂板悗鑷姩璁＄畻鐗瑰緛
    logging.info("daemon: 寮€濮嬭绠楃壒寰?..")
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
            logging.warning("daemon: 璁＄畻鐗瑰緛澶辫触 (%s): %s", ticker, e)
            feature_fail_count += 1

    logging.info(
        "daemon: 鐗瑰緛璁＄畻瀹屾垚锛屾垚鍔?%d锛屽け璐?%d", feature_success_count, feature_fail_count
    )
    save_status(
        {
            "last_data_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_feature_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "feature_success_count": feature_success_count,
            "feature_fail_count": feature_fail_count,
        }
    )


def _memory_guard(threshold_percent: int = 80) -> bool:
    """Memory guard: skip jobs when system memory usage is above threshold."""
    try:
        import gc
        import time
        import psutil
        mem = psutil.virtual_memory()
        if mem.percent > threshold_percent:
            logging.warning(
                "daemon: 鍐呭瓨浣跨敤鐜?%s%%锛岃秴杩囬槇鍊?%s%%锛屾殏鍋滀换鍔″苟閲婃斁鍐呭瓨",
                mem.percent, threshold_percent,
            )
            gc.collect()
            time.sleep(30)
            return False
    except Exception as e:
        logging.debug("daemon: memory_guard 妫€鏌ュ紓甯? %s", e)
    return True


def daily_analysis_job(cfg: Dict[str, Any]) -> None:
    """Run daily LLM analysis task."""


    if not _memory_guard():
        return
    try:
        from core.daily_analysis import run_daily_analysis_from_env

        logging.info("daemon: 寮€濮嬫墽琛屾瘡鏃ユ櫤鑳藉垎鏋愪换鍔?..")
        result = run_daily_analysis_from_env(include_market_review=True)
        save_status(
            {
                "last_daily_analysis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_daily_analysis_result": {
                    "result_count": len(result.get("results", [])),
                    "has_market_review": bool(result.get("market_review")),
                },
            }
        )
        logging.info("daemon: daily analysis job completed.")
    except Exception as e:
        logging.warning("daemon: 姣忔棩鏅鸿兘鍒嗘瀽浠诲姟澶辫触: %s", e)


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
    # 浣庨厤浼樺寲锛氱鐢?LSTM/GRU 鏃跺己鍒朵娇鐢?xgboost
    if model_type in ("lstm", "gru") and os.environ.get("DISABLE_HEAVY_MODELS", "").strip().lower() in ("1", "true", "yes"):
        logging.info("daemon: DISABLE_HEAVY_MODELS 宸插紑鍚紝灏?lstm/gru 鍥為€€涓?xgboost")
        model_type = "xgboost"
    auto_promote = training_config.get("auto_promote", True)
    generate_signals = training_config.get("generate_signals", True)

    logging.info("daemon: 寮€濮嬫ā鍨嬭缁冧换鍔★紝鏍囩殑鏁?%d锛屾ā鍨嬬被鍨?%s", len(universe), model_type)

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
            generate_signals=generate_signals
        )

        logging.info(
            "daemon: 璁粌浠诲姟瀹屾垚锛屾€昏=%d锛屾垚鍔?%d锛屾彁鍗?%d锛屽け璐?%d锛岃烦杩?%d",
            stats["total"],
            stats["trained"],
            stats["promoted"],
            stats["failed"],
            stats["skipped"],
        )

        save_status(
            {
                "last_training_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
        logging.error("daemon: 璁粌浠诲姟寮傚父: %s", e, exc_info=True)
        save_status(
            {
                "last_training_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "training_error": str(e),
            }
        )


def trading_job(cfg: Dict[str, Any]) -> None:
    """Run a single paper-trading rebalance task."""
    logging.warning(
        "daemon: automatic trading task is disabled by product policy (manual execution only)."
    )
    save_status({"last_trading_run": "disabled-by-policy"})


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
                        print(f"Warning: existing daemon process detected (PID={old_pid}).")
                        print(f"Current process PID={current_pid}, pid file will be overwritten.")
                except Exception:
                    pass
            else:
                try:
                    os.kill(old_pid, 0)
                    print(f"Warning: existing daemon process detected (PID={old_pid}).")
                    print(f"Current process PID={current_pid}, pid file will be overwritten.")
                except OSError:
                    pass
        except (ValueError, FileNotFoundError):
            pass

    # Write current process pid.
    try:
        with open(pid_file, "w", encoding="utf-8") as f:
            f.write(str(current_pid))
    except Exception as e:
        print(f"Warning: failed to write pid file {pid_file}: {e}")

    logging.basicConfig(
        filename=os.path.join(BASE_DIR, "logs", "daemon.log"),
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    cfg = load_config()
    logging.info("daemon: configuration loaded.")
    logging.info("daemon: process PID = %s", os.getpid())

    # Register scheduled jobs.
    setup_data_update_job(cfg.get("data_update", {}), lambda: data_update_job(cfg))
    logging.warning(
        "daemon: trading scheduler registration skipped by policy (manual/no auto-trading)."
    )
    setup_training_job(cfg.get("training", {}), lambda: training_job(cfg))
    setup_daily_analysis_job(cfg.get("daily_analysis", {}), lambda: daily_analysis_job(cfg))

    # Register daily settlement task (15:30 local time).
    try:
        import schedule
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
    except Exception as e:
        logging.warning("daemon: failed to register daily settlement job: %s", e)

    logging.info("daemon: scheduler loop started.")

    try:
        run_forever()
    except KeyboardInterrupt:
        logging.info("daemon: interrupt received, shutting down.")
    finally:
        # Cleanup pid file.
        try:
            if os.path.exists(pid_file):
                os.remove(pid_file)
        except Exception:
            pass


if __name__ == "__main__":
    main()


