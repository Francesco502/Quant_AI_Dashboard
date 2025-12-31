"""OHLCV 批量抓取与本地 Parquet 缓存工具

用途：
- 为本项目的本地数据仓库（`data/prices/.../*.parquet`）批量拉取并更新 OHLCV K 线；
- 默认数据源优先级：AkShare -> Tushare -> Binance -> AlphaVantage -> yfinance；
- 适合作为命令行脚本使用，也可以在其他模块中通过函数调用复用。

典型用法（命令行）：
--------------------

在项目根目录 `Quant_AI_Dashboard` 下执行：

```bash
# 示例 1：为少量标的抓取近 5 年的日线 OHLCV
python -m core.ohlcv_fetcher --tickers 600519.SS,000001.SZ,159755.SZ --days 1825

# 示例 2：复用 StockTradebyZ 的 stocklist.csv，抓取全 A 股约 10 年日线
python -m core.ohlcv_fetcher ^
  --stocklist ..\\abandoned\\StockTradebyZ_lab\\StockTradebyZ\\stocklist.csv ^
  --days 3650
```

说明：
- 本脚本只负责从远程数据源抓取并写入本地 Parquet，读取逻辑仍由 `core.data_service` / `core.data_store` 统一管理；
- 需要你在系统环境中配置好 `TUSHARE_TOKEN`（用于 Tushare）和 `ALPHA_VANTAGE_KEY`（用于 AlphaVantage，若需要）。
"""

from __future__ import annotations

import argparse
import os
from typing import List, Dict

import pandas as pd

from .data_service import _load_ohlcv_data_remote
from .data_store import save_local_ohlcv_history


def _parse_tickers_from_stocklist(path: str) -> List[str]:
    """从 CSV 股票清单中解析代码列表。

    优先顺序：
    - 若存在 `ts_code` 列（如 Tushare 导出的 A 股清单），使用该列；
    - 否则依次尝试 `ticker` / `symbol` 列；
    - 若均不存在，则抛出错误。
    """
    df = pd.read_csv(path)
    for col in ["ts_code", "ticker", "symbol"]:
        if col in df.columns:
            codes = df[col].astype(str).str.strip()
            # 过滤空值
            codes = [c for c in codes if c]
            return codes
    raise ValueError(
        f"无法在股票清单 {path} 中找到 ts_code/ticker/symbol 列，请检查文件格式。"
    )


def fetch_and_save_ohlcv_for_tickers(
    tickers: List[str],
    days: int = 3650,
    data_sources: List[str] | None = None,
    batch_size: int = 100,
) -> Dict[str, int]:
    """
    为指定标的批量抓取 OHLCV 并写入本地 Parquet 仓库。

    参数
    ----
    tickers:
        待抓取的标的列表（如 `["600519.SS", "000001.SZ", "BTC-USD"]`）。
    days:
        回看窗口长度（以天为单位）。例如 3650 表示约 10 年日线。
    data_sources:
        数据源优先级列表，默认 None 表示使用 `_load_ohlcv_data_remote` 的默认顺序：
        `["AkShare", "Tushare", "Binance", "AlphaVantage", "yfinance"]`。
    batch_size:
        每批次请求的标的数量，避免一次性请求过多导致远程源限流或内存压力。

    返回
    ----
    Dict[str, int] :
        一个字典，键为 ticker，值为成功写入的 K 线行数（0 表示未成功抓取）。
    """
    if not tickers:
        return {}

    # 从环境变量读取密钥（若存在）
    alpha_vantage_key = os.getenv("ALPHA_VANTAGE_KEY", None)
    tushare_token = os.getenv("TUSHARE_TOKEN", None)

    results: Dict[str, int] = {t: 0 for t in tickers}

    # 分批处理，避免一次性请求过多标的
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        print(f"[OHLCV Fetcher] 正在处理第 {i // batch_size + 1} 批，共 {len(batch)} 个标的...")

        remote_map = _load_ohlcv_data_remote(
            tickers=batch,
            days=days,
            data_sources=data_sources,
            alpha_vantage_key=alpha_vantage_key,
            tushare_token=tushare_token,
        )
        if not remote_map:
            print("  本批次未能从任何数据源获取到有效数据。")
            continue

        for t in batch:
            df = remote_map.get(t)
            if df is None or df.empty:
                print(f"  [跳过] {t}: 未获取到有效 OHLCV 数据。")
                continue
            try:
                save_local_ohlcv_history(t, df)
                results[t] = len(df)
                print(f"  [完成] {t}: 写入 {len(df)} 行 OHLCV 到本地 Parquet。")
            except Exception as e:
                print(f"  [失败] {t}: 写入本地 Parquet 时出错：{e}")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="批量抓取 OHLCV 日线并写入本地 Parquet 仓库（AkShare/Tushare/Binance/AlphaVantage/yfinance）。"
    )
    parser.add_argument(
        "--tickers",
        type=str,
        default="",
        help="逗号分隔的标的列表，如 '600519.SS,000001.SZ,BTC-USD'。",
    )
    parser.add_argument(
        "--stocklist",
        type=str,
        default="",
        help="可选：股票清单 CSV 路径（例如 StockTradebyZ 的 stocklist.csv）。"
        "若同时提供 --tickers，则两者合并去重。",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=3650,
        help="回看窗口天数（默认 3650 ≈ 10 年）。",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="每批处理的标的数量（默认 100）。",
    )

    args = parser.parse_args()

    tickers: List[str] = []

    if args.tickers:
        tickers.extend([t.strip() for t in args.tickers.split(",") if t.strip()])

    if args.stocklist:
        try:
            codes_from_csv = _parse_tickers_from_stocklist(args.stocklist)
            tickers.extend(codes_from_csv)
        except Exception as e:
            print(f"[错误] 解析股票清单 {args.stocklist} 失败：{e}")

    # 去重
    tickers = sorted(set(tickers))
    if not tickers:
        print("未提供任何有效的标的（tickers 或 stocklist 为空），程序退出。")
        return

    print(f"共解析到 {len(tickers)} 个标的，开始抓取最近 {args.days} 天的 OHLCV 日线...")
    results = fetch_and_save_ohlcv_for_tickers(
        tickers=tickers,
        days=args.days,
        data_sources=None,
        batch_size=args.batch_size,
    )

    success_count = sum(1 for _, n in results.items() if n > 0)
    print(
        f"[完成] 共 {len(tickers)} 个标的，其中 {success_count} 个成功写入本地 Parquet。"
    )


if __name__ == "__main__":
    main()


