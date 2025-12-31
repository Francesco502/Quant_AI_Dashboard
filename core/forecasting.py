import pandas as pd
import numpy as np


def simple_price_forecast(price_df: pd.DataFrame, horizon: int = 3) -> pd.DataFrame:
    """
    一个轻量级的价格预测 Demo 函数。

    设计思路：
    - 在真实项目中，此处应替换为 LSTM / Transformer 等时序模型；
      模型输入电池 SOH 项目中的 (V, I, T, cycle) 等特征，迁移为金融中的价格/成交量等特征。
    - 为了在面试 Demo 中快速跑通，这里用
        - 最近 N 日滑动平均 + 小幅随机扰动
      来近似未来 horizon 天的价格走势。

    参数
    ----
    price_df : pd.DataFrame
        列为不同资产的收盘价，行索引为日期。
    horizon : int
        预测天数。

    返回
    ----
    pd.DataFrame
        行为未来 horizon 天的“虚拟日期”，列为资产代码。
    """
    if price_df.empty:
        raise ValueError("price_df 为空，无法进行预测。")

    window = min(20, len(price_df))
    recent = price_df.tail(window)
    base = recent.mean(axis=0)

    last_date = price_df.index[-1]
    # 修复 pandas 2.0+ 兼容性：移除 closed 参数，从下一天开始生成日期
    # 使用 periods=horizon 生成 horizon 个交易日（不包含起始日期）
    try:
        # pandas 2.0+ 使用 inclusive 参数
        future_dates = pd.bdate_range(
            start=last_date + pd.Timedelta(days=1), 
            periods=horizon
        )
    except TypeError:
        # 旧版本 pandas 的回退方案
        future_dates = pd.bdate_range(
            start=last_date + pd.Timedelta(days=1), 
            periods=horizon,
            closed="right"
        )

    forecasts = []
    current = base.copy()

    for _ in range(horizon):
        noise = np.random.normal(loc=0.0, scale=0.01, size=len(base))
        current = current * (1 + noise)
        forecasts.append(current.copy())

    forecast_df = pd.DataFrame(forecasts, index=future_dates, columns=price_df.columns)
    return forecast_df


# 你可以在这里预留一个接口，把真实的 LSTM/Transformer 封装进来：
#
# def lstm_price_forecast(price_df: pd.DataFrame, horizon: int = 3) -> pd.DataFrame:
#     """
#     TODO: 使用你现有的电池 SOH LSTM 代码，迁移到价格预测。
#
#     面试时的讲解要点：
#     - 输入由 (时间步 x 特征维度) 的序列构成；
#     - 训练目标：多步价格预测或收益率预测；
#     - 只需要把电池数据的特征工程层，替换为金融时间序列的特征工程。
#     """
#     raise NotImplementedError("请在真实项目中接入你的 LSTM/Transformer 模型。")


