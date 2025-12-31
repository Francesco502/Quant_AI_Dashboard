"""后台守护进程（阶段 4）

职责：
- 长期运行在独立 Python 进程中；
- 周期性更新本地数据仓库；
- 周期性执行一次模拟交易决策（基于当前策略信号）；
- 将最近一次任务运行时间写入状态文件，供 Dashboard 查询。

运行方式示例（本机调试）：
    cd Quant_AI_Dashboard
    python -m core.daemon
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd

from . import data_store
from .data_service import load_price_data
from .data_updater import update_local_history_for_tickers
from .scheduler import setup_data_update_job, setup_trading_job, setup_training_job, run_forever
from .training_pipeline import TrainingPipeline
from .strategy_engine import generate_multi_asset_signals
from .strategy_manager import get_strategy_manager
from .trading_engine import apply_equal_weight_rebalance
from .account import ensure_account_dict
from .feature_store import get_feature_store
from .data_store import load_local_price_history


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "daemon_config.json")
STATUS_PATH = os.path.join(BASE_DIR, "daemon_status.json")
ACCOUNT_PATH = os.path.join(BASE_DIR, "data", "accounts", "paper_account_daemon.json")


def _ensure_dirs() -> None:
    os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, "data", "accounts"), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)


def load_config() -> Dict[str, Any]:
    """加载守护进程配置，不存在时创建一个默认示例"""
    if not os.path.exists(CONFIG_PATH):
        default = {
            "universe": ["159755.SZ", "002611", "006810", "160615", "013281"],
            "days": 365,
            "data_sources": ["AkShare", "Tushare"],
            "alpha_vantage_key": "",
            "tushare_token": "",
            "data_update": {
                "enabled": True,
                "interval_minutes": 60,
            },
            "trading": {
                "enabled": False,
                "interval_minutes": 60,
                "max_positions": 5,
                "initial_capital": 1_000_000.0,
            },
            "training": {
                "enabled": True,
                "time": "16:00",
                "model_type": "xgboost",  # 可选: "xgboost", "lightgbm", "random_forest", "lstm", "gru"
                "auto_promote": True,
                "generate_signals": True,
                "min_train_days": 60,
                "retrain_interval_days": 7,
                "min_improvement_threshold": 0.02,
            },
            "features": {
                "use_enhanced": True,
            },
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        return default

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_status(patch: Dict[str, Any]) -> None:
    """将最近状态写入状态文件（增量更新）"""
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
    """从文件加载模拟账户（守护进程版本）"""
    raw: Dict[str, Any] | None = None
    if os.path.exists(ACCOUNT_PATH):
        try:
            with open(ACCOUNT_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            raw = None
    account = ensure_account_dict(raw, initial_capital=1_000_000.0)
    return account


def _save_account(account: Dict[str, Any]) -> None:
    with open(ACCOUNT_PATH, "w", encoding="utf-8") as f:
        json.dump(account, f, ensure_ascii=False, indent=2)


def data_update_job(cfg: Dict[str, Any]) -> None:
    """数据更新任务：调用 data_updater 为 universe 列表增量更新本地仓库，并计算特征"""
    universe: List[str] = cfg.get("universe") or []
    if not universe:
        logging.warning("daemon: universe 为空，跳过数据更新任务。")
        return

    days = int(cfg.get("days", 365))
    data_sources = cfg.get("data_sources") or ["AkShare"]
    # 优先使用环境变量中的密钥，其次回退到配置文件，避免敏感信息硬编码
    alpha_vantage_key = (
        os.getenv("ALPHA_VANTAGE_KEY") or cfg.get("alpha_vantage_key") or ""
    )
    tushare_token = os.getenv("TUSHARE_TOKEN") or cfg.get("tushare_token") or ""

    logging.info("daemon: 开始数据更新任务，标的数=%d，窗口=%d 天", len(universe), days)
    update_local_history_for_tickers(
        tickers=universe,
        days=days,
        data_sources=data_sources,
        alpha_vantage_key=alpha_vantage_key,
        tushare_token=tushare_token,
    )
    logging.info("daemon: 数据更新任务完成。")

    # 阶段一：数据更新后自动计算特征
    logging.info("daemon: 开始计算特征...")
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
            logging.warning("daemon: 计算特征失败 (%s): %s", ticker, e)
            feature_fail_count += 1

    logging.info(
        "daemon: 特征计算完成，成功=%d，失败=%d", feature_success_count, feature_fail_count
    )
    save_status(
        {
            "last_data_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_feature_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "feature_success_count": feature_success_count,
            "feature_fail_count": feature_fail_count,
        }
    )


def training_job(cfg: Dict[str, Any]) -> None:
    """模型训练任务：批量训练模型并生成预测信号"""
    universe: List[str] = cfg.get("universe") or []
    if not universe:
        logging.warning("daemon: universe 为空，跳过训练任务。")
        return

    training_config = cfg.get("training", {})
    model_type = training_config.get("model_type", "xgboost")
    auto_promote = training_config.get("auto_promote", True)
    generate_signals = training_config.get("generate_signals", True)

    logging.info("daemon: 开始模型训练任务，标的数=%d，模型类型=%s", len(universe), model_type)

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
            "daemon: 训练任务完成，总计=%d，成功=%d，提升=%d，失败=%d，跳过=%d",
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
        logging.error("daemon: 训练任务异常: %s", e, exc_info=True)
        save_status(
            {
                "last_training_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "training_error": str(e),
            }
        )


def trading_job(cfg: Dict[str, Any]) -> None:
    """模拟交易任务：基于当前信号对账户进行一次调仓"""
    universe: List[str] = cfg.get("universe") or []
    if not universe:
        logging.warning("daemon: universe 为空，跳过交易任务。")
        return

    days = int(cfg.get("days", 365))
    data_sources = cfg.get("data_sources") or ["AkShare"]
    alpha_vantage_key = (
        os.getenv("ALPHA_VANTAGE_KEY") or cfg.get("alpha_vantage_key") or ""
    )
    tushare_token = os.getenv("TUSHARE_TOKEN") or cfg.get("tushare_token") or ""

    # 加载历史价格
    data = load_price_data(
        tickers=universe,
        days=days,
        data_sources=data_sources,
        alpha_vantage_key=alpha_vantage_key,
        tushare_token=tushare_token,
    )
    if data is None or data.empty:
        logging.warning("daemon: 交易任务加载数据为空，跳过。")
        return

    # 生成多资产交易信号（优先使用策略框架）
    strategy_id = cfg.get("trading", {}).get("strategy_id")
    signal_table = None
    
    if strategy_id:
        # 使用策略框架生成信号
        try:
            strategy_manager = get_strategy_manager()
            strategy = strategy_manager.get_strategy(strategy_id)
            if strategy:
                logging.info(f"daemon: 使用策略 {strategy_id} 生成信号")
                strategy_signals = strategy.generate_signals(data[universe], strategy_manager=strategy_manager)
                if not strategy_signals.empty:
                    # 转换为交易引擎需要的格式
                    signal_table = pd.DataFrame({
                        "ticker": strategy_signals["ticker"],
                        "last_price": [float(data[t].iloc[-1]) if t in data.columns else 0.0 for t in strategy_signals["ticker"]],
                        "combined_signal": strategy_signals["signal"],
                        "action": strategy_signals["action"],
                        "reason": strategy_signals.get("reason", ""),
                    })
        except Exception as e:
            logging.warning(f"daemon: 策略框架生成信号失败: {e}，回退到技术指标信号")
    
    # 如果策略框架未生成信号，使用技术指标信号
    if signal_table is None or signal_table.empty:
        signal_table = generate_multi_asset_signals(data[universe])
    
    if signal_table is None or signal_table.empty:
        logging.info("daemon: 当前无有效交易信号，跳过交易任务。")
        return

    # 加载账户并执行等权调仓
    account = _load_account()
    max_positions = int(cfg.get("trading", {}).get("max_positions", 5))
    initial_capital = float(cfg.get("trading", {}).get("initial_capital", 1_000_000.0))
    account["initial_capital"] = initial_capital

    account, msg = apply_equal_weight_rebalance(
        account=account,
        signal_table=signal_table,
        data=data,
        total_capital=initial_capital,
        max_positions=max_positions,
    )
    logging.info("daemon: 交易任务结果：%s", msg)
    _save_account(account)
    save_status({"last_trading_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})


def main() -> None:
    _ensure_dirs()

    # 写入 PID 文件，用于进程管理
    pid_file = os.path.join(BASE_DIR, "logs", "daemon.pid")
    current_pid = os.getpid()
    
    # 检查是否已有 PID 文件，如果存在且进程还在运行，则提示
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r", encoding="utf-8") as f:
                old_pid = int(f.read().strip())
            # 如果旧 PID 文件存在但进程已不存在，可以覆盖
            # 如果旧进程还在运行，则可能是重复启动
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
                        print(f"警告：检测到已有 daemon 进程（PID: {old_pid}）正在运行。")
                        print(f"当前进程 PID: {current_pid}，将覆盖 PID 文件。")
                except:
                    pass
            else:
                try:
                    os.kill(old_pid, 0)  # 检查进程是否存在
                    print(f"警告：检测到已有 daemon 进程（PID: {old_pid}）正在运行。")
                    print(f"当前进程 PID: {current_pid}，将覆盖 PID 文件。")
                except OSError:
                    pass
        except (ValueError, FileNotFoundError):
            pass
    
    # 写入当前进程的 PID
    try:
        with open(pid_file, "w", encoding="utf-8") as f:
            f.write(str(current_pid))
    except Exception as e:
        print(f"警告：无法写入 PID 文件 {pid_file}: {e}")

    logging.basicConfig(
        filename=os.path.join(BASE_DIR, "logs", "daemon.log"),
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    cfg = load_config()
    logging.info("daemon: 配置已加载。")
    logging.info(f"daemon: 进程 PID = {os.getpid()}")

    # 注册调度任务
    setup_data_update_job(cfg.get("data_update", {}), lambda: data_update_job(cfg))
    setup_trading_job(cfg.get("trading", {}), lambda: trading_job(cfg))
    setup_training_job(cfg.get("training", {}), lambda: training_job(cfg))

    logging.info("daemon: 开始进入调度循环 ...")
    
    try:
        run_forever()
    except KeyboardInterrupt:
        logging.info("daemon: 收到中断信号，正在退出...")
    finally:
        # 清理 PID 文件
        try:
            if os.path.exists(pid_file):
                os.remove(pid_file)
        except Exception:
            pass


if __name__ == "__main__":
    main()


