"""
AI预测页面模块

支持：
- 优先加载后台训练好的生产模型（离线训练 + 在线推理）
- 如果没有生产模型，回退到实时训练
- 显示模型来源和状态信息
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objs as go
from typing import Dict, Optional, Tuple, List
from datetime import datetime
from core.page_utils import get_ticker_names, get_selected_tickers, get_data
from core.forecasting import simple_price_forecast
from core.apple_ui import get_apple_chart_layout

# 尝试导入高级预测模块
try:
    from core.advanced_forecasting import (
        advanced_price_forecast,
        quick_predict,
        ProphetForecaster,
        XGBoostForecaster,
        LightGBMForecaster,
        ARIMAForecaster,
        RandomForestForecaster,
        LSTMForecaster,
        GRUForecaster,
        ModelEvaluator,
        ModelRegistry,
        ModelManager,
        PROPHET_AVAILABLE,
        XGBOOST_AVAILABLE,
        LIGHTGBM_AVAILABLE,
        STATSMODELS_AVAILABLE,
        SKLEARN_AVAILABLE,
        TORCH_AVAILABLE,
    )
    ADVANCED_FORECASTING_AVAILABLE = True
except ImportError:
    ADVANCED_FORECASTING_AVAILABLE = False
    PROPHET_AVAILABLE = False
    XGBOOST_AVAILABLE = False
    LIGHTGBM_AVAILABLE = False
    STATSMODELS_AVAILABLE = False
    SKLEARN_AVAILABLE = False
    TORCH_AVAILABLE = False
    quick_predict = None
    ModelRegistry = None
    ModelManager = None


def get_production_model_status(tickers: List[str]) -> Dict[str, Dict]:
    """
    获取各资产的生产模型状态
    
    返回:
        {ticker: {"has_model": bool, "model_id": str, "train_date": str, "metrics": dict}}
    """
    status = {}
    
    if not ADVANCED_FORECASTING_AVAILABLE or ModelRegistry is None:
        return {t: {"has_model": False} for t in tickers}
    
    try:
        registry = ModelRegistry()
        for ticker in tickers:
            model_id = registry.get_production_model(ticker)
            if model_id:
                model_info = registry.get_model_info(model_id)
                if model_info:
                    status[ticker] = {
                        "has_model": True,
                        "model_id": model_id,
                        "train_date": model_info.get("train_date", "未知"),
                        "model_type": model_info.get("model_type", "xgboost"),
                        "metrics": model_info.get("metrics", {}),
                        "status": model_info.get("status", "production"),
                    }
                else:
                    status[ticker] = {"has_model": False}
            else:
                status[ticker] = {"has_model": False}
    except Exception as e:
        print(f"获取模型状态失败: {e}")
        return {t: {"has_model": False} for t in tickers}
    
    return status


def predict_with_production_model(
    ticker: str,
    price_series: pd.Series,
    horizon: int = 5,
    use_enhanced_features: bool = True,
    model_type: str = "xgboost",
) -> Tuple[Optional[pd.DataFrame], str, Optional[str]]:
    """
    优先使用生产模型进行预测，如果没有则回退到实时训练
    
    参数:
        ticker: 标的代码
        price_series: 价格序列
        horizon: 预测天数
        use_enhanced_features: 是否使用增强特征
        model_type: 模型类型
        
    返回:
        (预测结果DataFrame, 模型来源描述, 模型ID)
        模型来源: "production" | "cached" | "realtime" | "fallback"
    """
    if not ADVANCED_FORECASTING_AVAILABLE or quick_predict is None:
        return None, "fallback", None
    
    # 1. 尝试使用生产模型（快速预测）
    try:
        pred = quick_predict(
            ticker=ticker,
            horizon=horizon,
            model_type=model_type,
            use_production_model=True,
            save_signal=False,
        )
        if pred is not None and not pred.empty:
            # 检查是从生产模型还是缓存获取
            registry = ModelRegistry()
            model_id = registry.get_production_model(ticker)
            if model_id:
                return pred, "production", model_id
            else:
                return pred, "cached", None
    except Exception as e:
        print(f"快速预测失败 ({ticker}, {model_type}): {e}")
    
    # 2. 回退到实时训练
    try:
        if model_type == "xgboost" and XGBOOST_AVAILABLE:
            forecaster = XGBoostForecaster(
                lookback=min(60, len(price_series)),
                use_enhanced_features=use_enhanced_features,
            )
            forecaster.fit(price_series)
            pred = forecaster.predict(horizon)
            return pred, "realtime", None
        elif model_type == "lightgbm" and LIGHTGBM_AVAILABLE:
            forecaster = LightGBMForecaster(
                lookback=min(60, len(price_series)),
                use_enhanced_features=use_enhanced_features,
            )
            forecaster.fit(price_series)
            pred = forecaster.predict(horizon)
            return pred, "realtime", None
        elif model_type == "random_forest" and SKLEARN_AVAILABLE:
            forecaster = RandomForestForecaster(
                lookback=min(60, len(price_series)),
                use_enhanced_features=use_enhanced_features,
            )
            forecaster.fit(price_series)
            pred = forecaster.predict(horizon)
            return pred, "realtime", None
        elif model_type == "lstm" and TORCH_AVAILABLE:
            forecaster = LSTMForecaster(
                sequence_length=min(30, len(price_series) // 2),
                epochs=50
            )
            forecaster.fit(price_series)
            pred = forecaster.predict(horizon)
            return pred, "realtime", None
        elif model_type == "gru" and TORCH_AVAILABLE:
            forecaster = GRUForecaster(
                sequence_length=min(30, len(price_series) // 2),
                epochs=50
            )
            forecaster.fit(price_series)
            pred = forecaster.predict(horizon)
            return pred, "realtime", None
    except Exception as e:
        print(f"实时训练失败 ({ticker}, {model_type}): {e}")
    
    return None, "fallback", None


def hybrid_price_forecast(
    price_df: pd.DataFrame,
    horizon: int = 5,
    model_type: str = "xgboost",
    use_enhanced_features: bool = False,
    prefer_production: bool = True,
) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    混合预测函数 - 优先使用生产模型，回退到实时训练
    
    参数:
        price_df: 价格数据
        horizon: 预测天数
        model_type: 模型类型
        use_enhanced_features: 是否使用增强特征
        prefer_production: 是否优先使用生产模型
        
    返回:
        (预测结果DataFrame, 各标的模型来源字典)
    """
    results = {}
    model_sources = {}
    
    last_date = price_df.index[-1]
    future_dates = pd.bdate_range(start=last_date + pd.Timedelta(days=1), periods=horizon)
    
    for ticker in price_df.columns:
        price_series = price_df[ticker].dropna()
        
        if len(price_series) < 30:
            # 数据不足，使用简单预测
            window = min(20, len(price_series))
            base = price_series.tail(window).mean()
            forecasts = [base * (1 + np.random.normal(0, 0.01)) for _ in range(horizon)]
            results[ticker] = forecasts
            model_sources[ticker] = "simple"
            continue
        
        pred = None
        source = "fallback"
        
        # 优先尝试生产模型（支持所有可训练模型）
        if prefer_production and model_type in ["xgboost", "lightgbm", "random_forest", "lstm", "gru"]:
            pred, source, _ = predict_with_production_model(
                ticker, price_series, horizon, use_enhanced_features, model_type
            )
            if pred is not None and not pred.empty:
                results[ticker] = pred["prediction"].values
                model_sources[ticker] = source
                continue
        
        # 回退到标准预测流程
        try:
            if model_type == "prophet" and PROPHET_AVAILABLE:
                forecaster = ProphetForecaster()
                forecaster.fit(price_series)
                pred = forecaster.predict(horizon)
                results[ticker] = pred["prediction"].values
                model_sources[ticker] = "realtime"
                
            elif model_type == "xgboost" and XGBOOST_AVAILABLE:
                forecaster = XGBoostForecaster(
                    lookback=min(60, len(price_series)),
                    use_enhanced_features=use_enhanced_features,
                )
                forecaster.fit(price_series)
                pred = forecaster.predict(horizon)
                results[ticker] = pred["prediction"].values
                model_sources[ticker] = "realtime"
                
            elif model_type == "lightgbm" and LIGHTGBM_AVAILABLE:
                forecaster = LightGBMForecaster(
                    lookback=min(60, len(price_series)),
                    use_enhanced_features=use_enhanced_features,
                )
                forecaster.fit(price_series)
                pred = forecaster.predict(horizon)
                results[ticker] = pred["prediction"].values
                model_sources[ticker] = "realtime"
                
            elif model_type == "arima" and STATSMODELS_AVAILABLE:
                forecaster = ARIMAForecaster()
                forecaster.fit(price_series)
                pred = forecaster.predict(horizon)
                results[ticker] = pred["prediction"].values
                model_sources[ticker] = "realtime"
                
            elif model_type == "random_forest" and SKLEARN_AVAILABLE:
                forecaster = RandomForestForecaster(
                    lookback=min(60, len(price_series)),
                    use_enhanced_features=use_enhanced_features,
                )
                forecaster.fit(price_series)
                pred = forecaster.predict(horizon)
                results[ticker] = pred["prediction"].values
                model_sources[ticker] = "realtime"
                
            elif model_type == "lstm" and TORCH_AVAILABLE:
                forecaster = LSTMForecaster(
                    sequence_length=min(30, len(price_series) // 2),
                    epochs=50
                )
                forecaster.fit(price_series)
                pred = forecaster.predict(horizon)
                results[ticker] = pred["prediction"].values
                model_sources[ticker] = "realtime"
                
            elif model_type == "gru" and TORCH_AVAILABLE:
                forecaster = GRUForecaster(
                    sequence_length=min(30, len(price_series) // 2),
                    epochs=50
                )
                forecaster.fit(price_series)
                pred = forecaster.predict(horizon)
                results[ticker] = pred["prediction"].values
                model_sources[ticker] = "realtime"
                
            else:
                # 简单预测
                window = min(20, len(price_series))
                base = price_series.tail(window).mean()
                forecasts = [base * (1 + np.random.normal(0, 0.01)) for _ in range(horizon)]
                results[ticker] = forecasts
                model_sources[ticker] = "simple"
                
        except Exception as e:
            print(f"预测 {ticker} 失败: {e}")
            window = min(20, len(price_series))
            base = price_series.tail(window).mean()
            forecasts = [base * (1 + np.random.normal(0, 0.01)) for _ in range(horizon)]
            results[ticker] = forecasts
            model_sources[ticker] = "fallback"
    
    result_df = pd.DataFrame(results, index=future_dates)
    return result_df, model_sources


def render_model_status_panel(tickers: List[str], model_sources: Dict[str, str]):
    """渲染模型状态面板"""
    model_status = get_production_model_status(tickers)
    
    # 统计
    production_count = sum(1 for s in model_sources.values() if s == "production")
    realtime_count = sum(1 for s in model_sources.values() if s == "realtime")
    cached_count = sum(1 for s in model_sources.values() if s == "cached")
    fallback_count = sum(1 for s in model_sources.values() if s in ["fallback", "simple"])
    
    # 显示摘要
    st.markdown("##### 模型来源")
    
    cols = st.columns(4)
    with cols[0]:
        st.metric("🏭 生产模型", production_count, help="使用后台训练好的离线模型")
    with cols[1]:
        st.metric("💾 缓存模型", cached_count, help="使用内存缓存的模型")
    with cols[2]:
        st.metric("⚡ 实时训练", realtime_count, help="本次请求实时训练的模型")
    with cols[3]:
        st.metric("📊 简单预测", fallback_count, help="数据不足或模型不可用时的回退方案")
    
    # 详细信息（可折叠）
    with st.expander("查看各资产模型详情", expanded=False):
        detail_data = []
        ticker_names = get_ticker_names()
        
        for ticker in tickers:
            source = model_sources.get(ticker, "unknown")
            status = model_status.get(ticker, {})
            
            source_labels = {
                "production": "🏭 生产模型",
                "cached": "💾 缓存模型",
                "realtime": "⚡ 实时训练",
                "simple": "📊 简单预测",
                "fallback": "📊 回退方案",
            }
            
            row = {
                "资产": ticker_names.get(ticker, ticker),
                "模型来源": source_labels.get(source, source),
            }
            
            if status.get("has_model"):
                row["模型ID"] = status.get("model_id", "-")[:12] + "..."
                row["训练日期"] = status.get("train_date", "-")
                metrics = status.get("metrics", {})
                if metrics:
                    row["方向准确率"] = f"{metrics.get('direction_accuracy', 0):.1%}"
            else:
                row["模型ID"] = "-"
                row["训练日期"] = "-"
                row["方向准确率"] = "-"
            
            detail_data.append(row)
        
        if detail_data:
            st.dataframe(pd.DataFrame(detail_data), hide_index=True, use_container_width=True)


def render_ai_forecast_page():
    """渲染AI预测页面"""
    ticker_names = get_ticker_names()
    tickers = get_selected_tickers()
    data = get_data()
    
    if data.empty or len(tickers) == 0:
        st.info("💡 提示：数据正在加载中，如果长时间未显示，请检查资产选择和数据源配置。")
        return
    
    # 固定使用T+5进行预测，但显示T+1、T+3、T+5三个结果
    forecast_horizon = 5
    
    # 紧凑的标题和说明
    col_title, col_info = st.columns([3, 1])
    with col_title:
        st.markdown("### AI 趋势预测")
    with col_info:
        st.caption("支持离线模型")
    
    # ===== 模型选择区域（紧凑布局）=====
    use_enhanced_features = False
    prefer_production = True
    
    if ADVANCED_FORECASTING_AVAILABLE:
        # 第一行：模型选择
        available_models = []
        if PROPHET_AVAILABLE:
            available_models.append("Prophet")
        if XGBOOST_AVAILABLE:
            available_models.append("XGBoost")
        if LIGHTGBM_AVAILABLE:
            available_models.append("LightGBM")
        if STATSMODELS_AVAILABLE:
            available_models.append("ARIMA")
        if SKLEARN_AVAILABLE:
            available_models.append("Random Forest")
        if TORCH_AVAILABLE:
            available_models.append("LSTM")
            available_models.append("GRU")
        if PROPHET_AVAILABLE or XGBOOST_AVAILABLE or TORCH_AVAILABLE:
            available_models.append("集成模型（Ensemble）")
        available_models.append("简单滑动平均")
        
        # 紧凑的模型选择布局
        col_model, col_prod, col_feat = st.columns([3, 1.5, 1.5])
        
        with col_model:
            forecast_model = st.selectbox(
                "选择预测模型",
                available_models,
                index=0,
                key="ai_forecast_model",
                help="不同模型各有优势：Prophet适合趋势预测，XGBoost适合多因子分析，LSTM适合捕捉序列模式"
            )
        
        with col_prod:
            # 所有可训练模型都支持生产模型
            if forecast_model in ["XGBoost", "LightGBM", "Random Forest", "LSTM", "GRU"]:
                prefer_production = st.checkbox(
                    "🏭 优先使用生产模型",
                    value=True,
                    help="优先加载后台训练好的离线模型（如果存在），实现毫秒级响应。",
                    key="prefer_production_model",
                )
        
        with col_feat:
            # 增强特征选项（适用于树模型）
            if forecast_model in ["XGBoost", "LightGBM", "Random Forest"]:
                use_enhanced_features = st.checkbox(
                    "增强特征",
                    value=True,
                    help="启用ATR/实现波动率等增强特征",
                    key="use_enhanced_features",
                )
        
        # 模型简介
        model_descriptions = {
            "Prophet": """
            **📈 Prophet（Facebook 开源）**
            - 自动处理季节性和节假日效应
            - 适合中长期趋势预测
            - 提供预测置信区间
            - 几乎无需调参，开箱即用
            """,
            "XGBoost": """
            **🌲 XGBoost（梯度提升树）**
            - 特征工程驱动，可解释性强
            - 支持多因子量化策略
            - **支持离线训练 + 在线推理**（毫秒级响应）
            - 可查看特征重要性排名
            """,
            "LightGBM": """
            **⚡ LightGBM（轻量级梯度提升）**
            - 训练速度快，内存占用小
            - 准确率高，适合大规模数据
            - 支持类别特征，无需独热编码
            - 在量化场景中表现优异
            """,
            "ARIMA": """
            **📊 ARIMA（自回归积分滑动平均）**
            - 经典时序模型，理论基础扎实
            - 适合平稳序列预测
            - 可解释性强，参数含义明确
            - 在金融时序分析中广泛应用
            """,
            "Random Forest": """
            **🌳 Random Forest（随机森林）**
            - 简单稳定，不易过拟合
            - 可解释性强，支持特征重要性
            - 对异常值不敏感
            - 适合作为基准模型对比
            """,
            "LSTM": """
            **🧠 LSTM（长短期记忆网络）**
            - 深度学习模型，序列记忆能力强
            - 适合捕捉短期时序模式
            - 可处理非线性关系
            - 需要较多数据训练
            """,
            "GRU": """
            **🔄 GRU（门控循环单元）**
            - 比 LSTM 更轻量，训练更快
            - 适合短期预测任务
            - 参数更少，不易过拟合
            - 在序列建模中表现优异
            """,
            "集成模型（Ensemble）": """
            **🧮 集成模型（Ensemble）**
            - 同时结合多个模型的预测结果
            - 通过加权平均提高稳健性，减少单一模型失效的风险
            - 适合作为"默认选择"，在不同市场环境下更平滑
            """,
            "简单滑动平均": """
            **📊 简单滑动平均**
            - 轻量快速，无需额外依赖
            - 适合快速原型验证
            - 基于历史均值的简单外推
            """
        }
        # 使用紧凑的信息框
        with st.expander("📖 模型说明", expanded=False):
            st.markdown(model_descriptions.get(forecast_model, ""))
        
        # 显示生产模型状态提示（紧凑显示，在同一行）
        if forecast_model in ["XGBoost", "LightGBM", "Random Forest", "LSTM", "GRU"] and prefer_production:
            model_status = get_production_model_status(tickers)
            prod_count = sum(1 for s in model_status.values() if s.get("has_model"))
            if prod_count > 0:
                st.caption(f"✅ {prod_count}/{len(tickers)} 个资产有生产模型可用")
            else:
                st.caption("⚠️ 无生产模型，将使用实时训练")
    else:
        forecast_model = "简单滑动平均"
        st.warning("⚠️ 高级预测模型未安装。请运行 `pip install -r requirements.txt` 安装 Prophet/XGBoost/PyTorch。")
    
    # ===== 预测执行 =====
    last_row = data.iloc[-1]
    model_sources = {}
    
    # 生成T+1、T+3、T+5三个预测结果
    horizons = [1, 3, 5]
    forecast_results = {}  # {horizon: forecast_df}
    
    with st.spinner(f"正在使用 {forecast_model} 进行预测（T+1, T+3, T+5）..."):
        for horizon in horizons:
            try:
                if forecast_model == "XGBoost" and XGBOOST_AVAILABLE:
                    forecast_df, model_sources = hybrid_price_forecast(
                        data[tickers],
                        horizon=horizon,
                        model_type="xgboost",
                        use_enhanced_features=use_enhanced_features,
                        prefer_production=prefer_production,
                    )
                elif forecast_model == "LightGBM" and LIGHTGBM_AVAILABLE:
                    forecast_df, model_sources = hybrid_price_forecast(
                        data[tickers],
                        horizon=horizon,
                        model_type="lightgbm",
                        use_enhanced_features=use_enhanced_features,
                        prefer_production=prefer_production,
                    )
                elif forecast_model == "ARIMA" and STATSMODELS_AVAILABLE:
                    forecast_df, model_sources = hybrid_price_forecast(
                        data[tickers],
                        horizon=horizon,
                        model_type="arima",
                        use_enhanced_features=False,
                        prefer_production=False,
                    )
                elif forecast_model == "Random Forest" and SKLEARN_AVAILABLE:
                    forecast_df, model_sources = hybrid_price_forecast(
                        data[tickers],
                        horizon=horizon,
                        model_type="random_forest",
                        use_enhanced_features=use_enhanced_features,
                        prefer_production=prefer_production,
                    )
                elif forecast_model == "LSTM" and TORCH_AVAILABLE:
                    forecast_df, model_sources = hybrid_price_forecast(
                        data[tickers],
                        horizon=horizon,
                        model_type="lstm",
                        use_enhanced_features=False,
                        prefer_production=prefer_production,
                    )
                elif forecast_model == "GRU" and TORCH_AVAILABLE:
                    forecast_df, model_sources = hybrid_price_forecast(
                        data[tickers],
                        horizon=horizon,
                        model_type="gru",
                        use_enhanced_features=False,
                        prefer_production=prefer_production,
                    )
                elif forecast_model == "Prophet" and PROPHET_AVAILABLE:
                    forecast_df = advanced_price_forecast(data, horizon=horizon, model_type='prophet')
                    model_sources = {t: "realtime" for t in tickers}
                elif forecast_model == "集成模型（Ensemble）":
                    forecast_df = advanced_price_forecast(data, horizon=horizon, model_type='ensemble', use_enhanced_features=use_enhanced_features)
                    model_sources = {t: "realtime" for t in tickers}
                else:
                    forecast_df = simple_price_forecast(data, horizon=horizon)
                    model_sources = {t: "simple" for t in tickers}
                
                forecast_results[horizon] = forecast_df
            except Exception as e:
                st.warning(f"预测T+{horizon}失败: {e}")
                forecast_results[horizon] = None
    
    # 使用T+5的结果作为主要预测结果（用于曲线绘制）
    forecast_df = forecast_results.get(5)
    if forecast_df is None:
        st.error("预测失败，请检查模型配置和数据")
        return
    
    # 显示模型来源信息（紧凑显示，放在预测详情标题旁）
    col_detail, col_status = st.columns([3, 1])
    with col_detail:
        st.markdown("#### 预测详情")
    with col_status:
        if model_sources:
            production_count = sum(1 for s in model_sources.values() if s == "production")
            realtime_count = sum(1 for s in model_sources.values() if s == "realtime")
            if production_count > 0:
                st.caption(f"🏭{production_count} ⚡{realtime_count}")
    
    # 预测结果表格 - 显示T+1、T+3、T+5
    forecast_data = []
    for ticker in tickers:
        if ticker not in data.columns:
            continue
        
        last_price = last_row[ticker]
        currency = "¥" if (".SZ" in ticker or ".SS" in ticker or (ticker.isdigit() and len(ticker) == 6)) else "$"
        display_name = ticker_names.get(ticker, ticker)
        
        # 模型来源标签
        source = model_sources.get(ticker, "unknown")
        source_labels = {
            "production": "🏭",
            "cached": "💾",
            "realtime": "⚡",
            "simple": "📊",
            "fallback": "📊",
        }
        source_label = source_labels.get(source, "")
        
        # 获取T+1、T+3、T+5的预测结果
        pred_t1 = None
        pred_t3 = None
        pred_t5 = None
        delta_t1 = None
        delta_t3 = None
        delta_t5 = None
        
        if forecast_results.get(1) is not None and ticker in forecast_results[1].columns and len(forecast_results[1]) > 0:
            pred_t1 = forecast_results[1][ticker].iloc[0]  # T+1是第1个预测点
            delta_t1 = (pred_t1 - last_price) / last_price
        
        if forecast_results.get(3) is not None and ticker in forecast_results[3].columns and len(forecast_results[3]) > 2:
            pred_t3 = forecast_results[3][ticker].iloc[2]  # T+3是第3个预测点（索引2）
            delta_t3 = (pred_t3 - last_price) / last_price
        
        if forecast_results.get(5) is not None and ticker in forecast_results[5].columns and len(forecast_results[5]) > 4:
            pred_t5 = forecast_results[5][ticker].iloc[4]  # T+5是第5个预测点（索引4）
            delta_t5 = (pred_t5 - last_price) / last_price
        
        forecast_data.append({
            "资产": f"{source_label} {display_name}",
            "当前价格": f"{currency}{last_price:,.2f}",
            "T+1 预测": f"{currency}{pred_t1:,.2f}" if pred_t1 is not None else "-",
            "T+1 变化": f"{delta_t1:+.2%}" if delta_t1 is not None else "-",
            "T+3 预测": f"{currency}{pred_t3:,.2f}" if pred_t3 is not None else "-",
            "T+3 变化": f"{delta_t3:+.2%}" if delta_t3 is not None else "-",
            "T+5 预测": f"{currency}{pred_t5:,.2f}" if pred_t5 is not None else "-",
            "T+5 变化": f"{delta_t5:+.2%}" if delta_t5 is not None else "-",
        })
    
    if forecast_data:
        st.dataframe(
            pd.DataFrame(forecast_data),
            use_container_width=True,
            hide_index=True,
        )
    
    # ===== 预测曲线（T+5）=====
    st.markdown("#### 预测曲线（T+5）")
    
    fig_forecast = go.Figure()
    history_window = min(60, len(data))
    history_end_date = data.index[-1]
    future_start_date = forecast_df.index[0] if len(forecast_df.index) > 0 else None
    future_end_date = forecast_df.index[-1] if len(forecast_df.index) > 0 else None
    
    for ticker in [t for t in tickers if t in data.columns]:
        if ticker in forecast_df.columns:
            hist = data[ticker].iloc[-history_window:]
            display_name = ticker_names.get(ticker, ticker)
            
            # 根据模型来源调整线条样式
            source = model_sources.get(ticker, "unknown")
            line_dash = "solid" if source == "production" else "dash"
            
            fig_forecast.add_trace(go.Scatter(
                x=hist.index, y=hist.values,
                mode="lines", name=f"{display_name} 历史",
                line=dict(width=2)
            ))
            fig_forecast.add_trace(go.Scatter(
                x=forecast_df.index, y=forecast_df[ticker].values,
                mode="lines", name=f"{display_name} 预测",
                line=dict(dash=line_dash, width=2)
            ))
    
    # 预测区域背景
    if future_start_date is not None and future_end_date is not None:
        fig_forecast.add_shape(
            type="rect", xref="x", yref="paper",
            x0=future_start_date, x1=future_end_date, y0=0, y1=1,
            fillcolor="rgba(0,122,255,0.06)", line_width=0, layer="below"
        )
    
    # 分界线
    fig_forecast.add_shape(
        type="line", xref="x", yref="paper",
        x0=history_end_date, x1=history_end_date, y0=0, y1=1,
        line=dict(color="rgba(60,60,67,0.5)", width=1, dash="dot")
    )
    fig_forecast.add_annotation(
        x=history_end_date, y=1.02, xref="x", yref="paper",
        showarrow=False, text="预测起点",
        font=dict(size=11, color="rgba(60,60,67,0.8)")
    )
    
    # AI 预测曲线图
    has_chinese_asset = any(".SZ" in t or ".SS" in t for t in tickers) or any(t.isdigit() and len(t) == 6 for t in tickers)
    has_us_asset = any(t in ["BTC-USD", "ETH-USD", "AAPL", "TSLA", "NVDA"] for t in tickers)
    forecast_yaxis_title = "价格 (USD / CNY)" if (has_chinese_asset and has_us_asset) else ("价格 (CNY)" if has_chinese_asset else "价格 (USD)")
    
    fig_forecast.update_layout(**get_apple_chart_layout(
        title="AI 预测曲线（T+5）",
        height=380,
        xaxis_title="日期",
        yaxis_title=forecast_yaxis_title,
    ))
    st.plotly_chart(fig_forecast, use_container_width=True, key="chart_forecast")
    
    # ===== 模型评估（Walk-forward 验证） =====
    if ADVANCED_FORECASTING_AVAILABLE:
        with st.expander("🔬 模型评估（Walk-forward 验证）", expanded=False):
            st.caption("对单个资产在历史数据上进行滚动验证，对比不同模型的预测精度和交易表现。")
            
            # 第一行：选择评估资产
            eval_ticker = st.selectbox(
                "选择评估资产", tickers, index=0, key="ai_eval_ticker"
            )
            
            # 第二行：折数和每折测试长度
            eval_col2, eval_col3 = st.columns([1, 1])
            with eval_col2:
                n_splits = st.select_slider(
                    "折数", options=[3, 4, 5], value=5, key="ai_n_splits",
                    help="将历史数据按时间顺序切成若干折做滚动验证"
                )
            with eval_col3:
                test_size = st.select_slider(
                    "每折测试长度（天）", options=[20, 40, 60], value=20, key="ai_test_size",
                    help="每一折中用来评估模型的测试集天数"
                )
            
            if st.button("运行模型评估", key="ai_run_eval"):
                price_series = data[eval_ticker].dropna()
                if len(price_series) < n_splits * test_size + 60:
                    st.warning("可用历史数据不足以进行所选参数的滚动验证，请减少折数或测试长度。")
                else:
                    with st.spinner("正在对各模型进行滚动评估（可能需要几分钟）..."):
                        eval_results = []
                        model_classes = []
                        if PROPHET_AVAILABLE:
                            model_classes.append(("Prophet", ProphetForecaster))
                        if XGBOOST_AVAILABLE:
                            model_classes.append(("XGBoost", XGBoostForecaster))
                        if LIGHTGBM_AVAILABLE:
                            model_classes.append(("LightGBM", LightGBMForecaster))
                        if STATSMODELS_AVAILABLE:
                            model_classes.append(("ARIMA", ARIMAForecaster))
                        if SKLEARN_AVAILABLE:
                            model_classes.append(("Random Forest", RandomForestForecaster))
                        if TORCH_AVAILABLE:
                            model_classes.append(("LSTM", LSTMForecaster))
                            model_classes.append(("GRU", GRUForecaster))
                        
                        progress_bar = st.progress(0)
                        for i, (name, cls) in enumerate(model_classes):
                            try:
                                df_eval = ModelEvaluator.walk_forward_validation(
                                    price_series, cls, n_splits=n_splits, test_size=test_size
                                )
                                if not df_eval.empty:
                                    summary = df_eval.mean(numeric_only=True)
                                    summary["model"] = name
                                    eval_results.append(summary)
                            except Exception as e:
                                st.warning(f"{name} 评估失败：{e}")
                            progress_bar.progress((i + 1) / len(model_classes))
                        progress_bar.empty()
                        
                        if not eval_results:
                            st.info("当前参数下未能得到有效的评估结果。")
                        else:
                            summary_df = pd.DataFrame(eval_results).set_index("model")
                            best_by_rmse = summary_df["RMSE"].idxmin()
                            best_by_dir = summary_df["Direction_Accuracy"].idxmax()
                            
                            st.markdown("##### 各模型评估指标（均值）")
                            display_cols = ["MAE", "RMSE", "MAPE", "Direction_Accuracy", "Strategy_CumReturn", "Strategy_Sharpe"]
                            available_cols = [c for c in display_cols if c in summary_df.columns]
                            st.dataframe(summary_df[available_cols], use_container_width=True)
                            
                            st.success(
                                f"**推荐模型：** `{best_by_rmse}` "
                                f"（RMSE 最优：{summary_df.loc[best_by_rmse, 'RMSE']:.4f}；"
                                f"方向准确率：{summary_df.loc[best_by_rmse, 'Direction_Accuracy']:.1f}%）"
                            )
                            if best_by_rmse != best_by_dir:
                                st.caption(
                                    f"💡 RMSE 最优为 {best_by_rmse}，方向准确率最高为 {best_by_dir}，"
                                    "可根据偏好在误差与方向之间权衡。"
                                )
