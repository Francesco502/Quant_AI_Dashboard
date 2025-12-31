"""
Quant-AI-Dashboard 主应用
集成：数据获取、技术指标、风险分析、回测、相关性分析等功能
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objs as go
import plotly.express as px
import yfinance as yf
import time
import warnings
import requests
import json
import os
import logging
from typing import List
from datetime import datetime, timedelta
import hashlib

# 配置日志级别，减少 cmdstanpy（Prophet 模型）的 INFO 日志输出
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)

# 尝试导入 bcrypt（用于密码哈希）
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False
    bcrypt = None

# 核心模块导入
from core.forecasting import simple_price_forecast
from core.portfolio import optimize_portfolio_markowitz

# Apple Design System UI 模块
from core.apple_ui import (
    render_compact_header,
    render_section_header,
    render_section_divider,
    get_apple_chart_layout,
    get_apple_line_colors,
    apply_apple_theme_to_figure,
    APPLE_COLORS,
)

# 高级预测模块（可选）
try:
    from core.advanced_forecasting import (
        advanced_price_forecast,
        get_available_models,
        ProphetForecaster,
        XGBoostForecaster,
        LSTMForecaster,
        ModelEvaluator,
        PROPHET_AVAILABLE,
        XGBOOST_AVAILABLE,
        TORCH_AVAILABLE,
    )
    ADVANCED_FORECASTING_AVAILABLE = True
except ImportError:
    ADVANCED_FORECASTING_AVAILABLE = False
    PROPHET_AVAILABLE = False
    XGBOOST_AVAILABLE = False
    TORCH_AVAILABLE = False
from core.technical_indicators import (
    calculate_all_indicators,
    get_trading_signals
)
from core.cache_utils import (
    calculate_returns_cached,
    calculate_indicators_cached,
    get_trading_signals_cached,
    calculate_correlation_matrix_cached,
    calculate_covariance_matrix_cached,
)
from core.risk_analysis import (
    calculate_var,
    calculate_cvar,
    calculate_max_drawdown,
    calculate_correlation_matrix,
    calculate_portfolio_risk_metrics,
    calculate_risk_contribution
)
from core.backtest import SimpleBacktest, simple_ma_strategy
from core.correlation import (
    calculate_rolling_correlation,
    find_highly_correlated_pairs,
)
from core.glossary import FINANCIAL_GLOSSARY, get_tooltip_html, get_inline_explanation
from core.stocktradebyz_adapter import (
    run_selectors_for_market,
    get_default_selector_configs,
    generate_selector_signals_for_series,
    STOCKTRADEBYZ_AVAILABLE,
)
from core.error_handler import handle_error, safe_execute, DashboardError
from core.error_ui import (
    show_user_friendly_error,
    show_data_fetch_error,
    show_rate_limit_error,
    show_network_error,
)
from core.app_utils import save_user_state
from core.version import VERSION, get_version_info
from core.data_quality import DataQualityChecker, QualityLevel

# 尝试导入 AkShare（用于A股/ETF数据）
try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    ak = None

st.set_page_config(
    page_title="Quant-AI-Dashboard",
    page_icon="💹",  # 使用更专业的图标
    layout="wide",
    initial_sidebar_state="expanded"
)
warnings.filterwarnings("ignore", category=FutureWarning)

# 加载自定义CSS
def load_custom_css():
    """加载Apple风格的自定义CSS（模块化结构）"""
    css_parts = []
    
    # 1. 加载主样式文件（如果存在）
    try:
        with open('.streamlit/style.css', 'r', encoding='utf-8') as f:
            css_parts.append(f.read())
    except FileNotFoundError:
        pass
    
    # 2. 加载模块化 CSS 文件（如果存在）
    module_files = [
        '.streamlit/css/variables.css',
        '.streamlit/css/components/checkbox.css',
        '.streamlit/css/components/buttons.css',
    ]
    
    for file_path in module_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                css_parts.append(f.read())
        except FileNotFoundError:
            # 模块文件不存在时跳过（向后兼容）
            pass
    
    # 合并所有 CSS
    if css_parts:
        combined_css = '\n\n'.join(css_parts)
        st.markdown(f'<style>{combined_css}</style>', unsafe_allow_html=True)
    else:
        # 如果所有文件都不存在，使用最小化的 fallback 样式
        st.markdown("""
        <style>
        .main .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 1200px; }
        </style>
        """, unsafe_allow_html=True)

load_custom_css()


# ==================== 本地用户状态与模拟账户持久化 ====================

USER_STATE_FILE = os.path.join(".streamlit", "user_state.json")
PAPER_ACCOUNT_FILE = os.path.join(".streamlit", "paper_account.json")

# 优先从环境变量读取 API 密钥，避免明文写入代码或配置文件
DEFAULT_ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "")
DEFAULT_TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")


def load_user_state() -> dict:
    """从本地文件加载用户状态（资产池、数据源等），用于在刷新或代码修改后保持设置"""
    try:
        if os.path.exists(USER_STATE_FILE):
            with open(USER_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"加载用户状态失败: {e}")
    return {}


# save_user_state 已移至 core/app_utils.py


def load_paper_account() -> dict | None:
    """从本地文件加载模拟账户状态（纸面账户）"""
    try:
        if os.path.exists(PAPER_ACCOUNT_FILE):
            with open(PAPER_ACCOUNT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"加载模拟账户失败: {e}")
    return None


def save_paper_account() -> None:
    """将当前会话中的模拟账户状态持久化到本地文件"""
    try:
        account = st.session_state.get("paper_account")
        if not account:
            return

        os.makedirs(os.path.dirname(PAPER_ACCOUNT_FILE), exist_ok=True)

        def _default(obj):
            # 支持 datetime 等不可直接序列化的对象
            if isinstance(obj, datetime):
                return obj.isoformat()
            return str(obj)

        with open(PAPER_ACCOUNT_FILE, "w", encoding="utf-8") as f:
            json.dump(account, f, ensure_ascii=False, indent=2, default=_default)
    except Exception as e:
        print(f"保存模拟账户失败: {e}")


from core.data_service import load_price_data, load_ohlcv_data


# ==================== 登录认证系统 ====================

# 登录配置文件路径
LOGIN_CONFIG_FILE = os.path.join(".streamlit", "login_config.json")

# 尝试加载 .env 文件（如果存在 python-dotenv）
try:
    from dotenv import load_dotenv
    load_dotenv()  # 自动加载项目根目录的 .env 文件
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


def load_login_config() -> dict:
    """从本地配置文件加载登录密码配置"""
    try:
        if os.path.exists(LOGIN_CONFIG_FILE):
            with open(LOGIN_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"加载登录配置失败: {e}")
    return {}


def save_login_config(password: str = "", password_hash: str = "") -> None:
    """保存登录密码配置到本地文件"""
    try:
        os.makedirs(os.path.dirname(LOGIN_CONFIG_FILE), exist_ok=True)
        config = {}
        if password:
            config["password"] = password
        if password_hash:
            config["password_hash"] = password_hash
        with open(LOGIN_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存登录配置失败: {e}")


# 密码读取优先级（从高到低）：
# 1. 环境变量（APP_LOGIN_PASSWORD 或 APP_LOGIN_PASSWORD_HASH）
# 2. .env 文件（如果安装了 python-dotenv）
# 3. 本地配置文件（.streamlit/login_config.json）

def get_login_password_config():
    """动态获取登录密码配置（每次调用时重新读取，支持运行时更新）
    
    Returns:
        (password, password_hash) 元组
    """
    # 从环境变量读取（包括从 .env 文件加载的）
    password = os.getenv("APP_LOGIN_PASSWORD", "")
    password_hash = os.getenv("APP_LOGIN_PASSWORD_HASH", "")
    
    # 如果环境变量中没有，尝试从本地配置文件读取
    if not password and not password_hash:
        login_config = load_login_config()
        password = login_config.get("password", "")
        password_hash = login_config.get("password_hash", "")
    
    return password, password_hash


def is_login_enabled() -> bool:
    """检查是否启用了登录功能"""
    password, password_hash = get_login_password_config()
    return bool(password or password_hash)


def hash_password(password: str) -> str:
    """使用 bcrypt 生成密码哈希（用于首次设置密码）"""
    if not BCRYPT_AVAILABLE:
        # 如果没有 bcrypt，使用 SHA256 作为后备（安全性较低，但可用）
        return hashlib.sha256(password.encode()).hexdigest()
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(input_password: str, stored_password_or_hash: str) -> bool:
    """验证密码是否正确
    
    Args:
        input_password: 用户输入的密码
        stored_password_or_hash: 存储的密码（明文）或哈希值
    
    Returns:
        True 如果密码正确，False 否则
    """
    if not stored_password_or_hash:
        return False
    
    # 如果存储的是 bcrypt 哈希（以 $2b$ 开头）
    if stored_password_or_hash.startswith("$2b$") or stored_password_or_hash.startswith("$2a$"):
        if not BCRYPT_AVAILABLE:
            st.error("系统错误：需要 bcrypt 库来验证密码哈希。请运行: pip install bcrypt")
            return False
        try:
            return bcrypt.checkpw(input_password.encode('utf-8'), stored_password_or_hash.encode('utf-8'))
        except Exception:
            return False
    
    # 如果存储的是 SHA256 哈希（64 字符的十六进制字符串）
    if len(stored_password_or_hash) == 64 and all(c in '0123456789abcdef' for c in stored_password_or_hash.lower()):
        input_hash = hashlib.sha256(input_password.encode()).hexdigest()
        return input_hash == stored_password_or_hash.lower()
    
    # 否则视为明文密码（直接比对，不推荐用于生产环境）
    return input_password == stored_password_or_hash


def render_login_page() -> bool:
    """渲染登录页面，返回 True 如果登录成功"""
    # 按钮样式已统一在 CSS 文件中管理，无需重复定义
    
    # 使用 Streamlit 列布局创建居中效果
    # 左右两侧留白，中间放登录框
    spacer_left, login_col, spacer_right = st.columns([1, 2, 1])
    
    with login_col:
        # 顶部留白
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        
        # 登录卡片（使用 Streamlit 原生容器）
        with st.container(border=False):
            # 标题
            st.markdown(
                "<h2 style='text-align: center; color: #1D1D1F; margin-bottom: 0.5rem;'>访问验证</h2>",
                unsafe_allow_html=True
            )
            
            # 副标题
            st.markdown(
                "<p style='text-align: center; color: #86868B; margin-bottom: 1.5rem;'>请输入访问密码以继续</p>",
                unsafe_allow_html=True
            )
            
            # 密码输入框
            password_input = st.text_input(
                "访问密码",
                type="password",
                key="login_password_input",
                label_visibility="visible"
            )
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # 按钮区域
            btn_col1, btn_col2 = st.columns([1, 1])
            with btn_col1:
                login_button = st.button("登录", type="primary")
            with btn_col2:
                cancel_button = st.button("取消")
            
            if cancel_button:
                st.stop()
    
    # 处理登录逻辑
    if login_button:
        if not password_input:
            with login_col:
                st.error("请输入密码")
            return False
        
        # 动态获取密码配置
        password, password_hash = get_login_password_config()
        stored_password = password_hash if password_hash else password
        
        if verify_password(password_input, stored_password):
            st.session_state["authenticated"] = True
            with login_col:
                st.success("登录成功！")
            time.sleep(0.5)  # 短暂延迟以显示成功消息
            st.rerun()
        else:
            with login_col:
                st.error("密码错误，请重试")
            return False
    
    return False


def render_first_time_setup() -> bool:
    """首次运行时的密码设置页面，返回 True 如果设置成功"""
    # 按钮样式已统一在 CSS 文件中管理，无需重复定义
    
    # 使用 Streamlit 列布局创建居中效果
    spacer_left, setup_col, spacer_right = st.columns([1, 2, 1])
    
    with setup_col:
        # 顶部留白
        st.markdown("<br><br>", unsafe_allow_html=True)
        
        # 设置卡片
        with st.container(border=True):
            # 标题
            st.markdown(
                "<h2 style='text-align: center; color: #1D1D1F; margin-bottom: 0.5rem;'>🔐 首次设置</h2>",
                unsafe_allow_html=True
            )
            
            # 副标题
            st.markdown(
                "<p style='text-align: center; color: #86868B; margin-bottom: 1.5rem; line-height: 1.6;'>检测到这是首次运行，请设置访问密码以保护您的系统</p>",
                unsafe_allow_html=True
            )
            
            # 设置选项
            use_hash = st.checkbox(
                "使用密码哈希（推荐，更安全）",
                value=True,
                help="密码将以加密哈希形式存储，即使配置文件泄露也无法直接获取原始密码"
            )
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # 密码输入
            password1 = st.text_input(
                "设置密码",
                type="password",
                key="setup_password1",
                help="密码将用于后续访问系统"
            )
            
            password2 = st.text_input(
                "确认密码",
                type="password",
                key="setup_password2",
                help="请再次输入密码以确认"
            )
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # 按钮区域
            btn_col1, btn_col2 = st.columns([1, 1])
            with btn_col1:
                setup_button = st.button("完成设置", type="primary")
            with btn_col2:
                skip_button = st.button("跳过（开发模式）")
    
    # 处理设置逻辑
    if setup_button:
        if not password1:
            with setup_col:
                st.error("请输入密码")
            return False
        
        if password1 != password2:
            with setup_col:
                st.error("两次输入的密码不一致，请重新输入")
            return False
        
        if len(password1) < 4:
            with setup_col:
                st.error("密码长度至少为 4 个字符")
            return False
        
        # 保存密码配置
        try:
            if use_hash:
                password_hash = hash_password(password1)
                save_login_config(password_hash=password_hash)
                with setup_col:
                    st.success("密码已设置（使用哈希加密）！")
            else:
                save_login_config(password=password1)
                with setup_col:
                    st.success("密码已设置！")
                    st.warning("⚠️ 提示：明文密码仅适合开发环境，生产环境建议使用哈希模式")
            
            with setup_col:
                st.info("正在重新加载...")
            time.sleep(1)
            st.rerun()  # 重新运行以加载新配置
        except Exception as e:
            with setup_col:
                st.error(f"保存配置失败: {e}")
            return False
    
    if skip_button:
        with setup_col:
            st.info("已跳过密码设置，系统将以开发模式运行（无需登录）")
        # 创建一个标记文件，表示用户已选择跳过
        skip_marker = os.path.join(".streamlit", ".skip_password_setup")
        try:
            os.makedirs(os.path.dirname(skip_marker), exist_ok=True)
            with open(skip_marker, "w") as f:
                f.write("skipped")
        except:
            pass
        time.sleep(1)
        st.rerun()
    
    return False


# ==================== 数据仓库监控组件 ====================

def render_data_warehouse_monitor():
    """渲染数据仓库监控面板，显示本地数据统计和选股结果保存状态"""
    from pathlib import Path
    from core.data_store import BASE_DIR
    from datetime import datetime
    
    try:
        base_path = Path(BASE_DIR)
        
        # 统计行情数据
        prices_dir = base_path / "prices"
        price_stats = {}
        total_price_files = 0
        price_date_ranges = {}
        
        if prices_dir.exists():
            for market_dir in prices_dir.iterdir():
                if market_dir.is_dir():
                    market_name = market_dir.name
                    parquet_files = list(market_dir.glob("*.parquet"))
                    count = len(parquet_files)
                    price_stats[market_name] = count
                    total_price_files += count
                    
                    # 尝试获取日期范围（采样几个文件）
                    if count > 0:
                        sample_files = parquet_files[:min(5, count)]
                        date_ranges = []
                        for pf in sample_files:
                            try:
                                df = pd.read_parquet(pf)
                                if not df.empty and isinstance(df.index, pd.DatetimeIndex):
                                    date_ranges.append((df.index.min(), df.index.max()))
                            except:
                                pass
                        if date_ranges:
                            min_date = min(d[0] for d in date_ranges)
                            max_date = max(d[1] for d in date_ranges)
                            price_date_ranges[market_name] = (min_date, max_date)
        
        # 统计选股结果
        signals_dir = base_path / "signals"
        selector_dir = signals_dir / "z_selectors" if signals_dir.exists() else None
        selector_files = []
        latest_selector_date = None
        
        if selector_dir and selector_dir.exists():
            selector_files = sorted(selector_dir.glob("*.csv"), key=lambda x: x.stat().st_mtime, reverse=True)
            if selector_files:
                # 从文件名提取日期（格式：YYYY-MM-DD.csv）
                try:
                    latest_file = selector_files[0]
                    date_str = latest_file.stem
                    latest_selector_date = pd.to_datetime(date_str)
                except:
                    pass
        
        # 显示统计信息
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "行情数据文件",
                f"{total_price_files:,}",
                help="本地存储的股票行情数据文件总数"
            )
        
        with col2:
            a_stock_count = price_stats.get("A股", 0)
            st.metric(
                "A股数据",
                f"{a_stock_count:,}",
                help="A股市场的数据文件数量"
            )
        
        with col3:
            selector_count = len(selector_files)
            st.metric(
                "选股结果文件",
                f"{selector_count}",
                help="已保存的选股结果文件数量"
            )
        
        with col4:
            if latest_selector_date:
                days_ago = (datetime.now() - latest_selector_date.to_pydatetime()).days
                st.metric(
                    "最近选股",
                    f"{days_ago}天前" if days_ago > 0 else "今天",
                    help="最近一次选股结果保存的时间"
                )
            else:
                st.metric(
                    "最近选股",
                    "无",
                    help="尚未保存任何选股结果"
                )
        
        # 详细统计表格
        with st.expander("📁 详细数据统计", expanded=False):
            if price_stats:
                st.markdown("**行情数据分布：**")
                stats_df = pd.DataFrame([
                    {
                        "市场": market,
                        "文件数": count,
                        "数据日期范围": f"{price_date_ranges.get(market, (None, None))[0].strftime('%Y-%m-%d') if price_date_ranges.get(market) and price_date_ranges[market][0] else 'N/A'} ~ {price_date_ranges.get(market, (None, None))[1].strftime('%Y-%m-%d') if price_date_ranges.get(market) and price_date_ranges[market][1] else 'N/A'}"
                    }
                    for market, count in sorted(price_stats.items())
                ])
                st.dataframe(stats_df, hide_index=True, width='stretch')
            
            if selector_files:
                st.markdown("**最近选股结果：**")
                selector_list = []
                for sf in selector_files[:10]:  # 只显示最近10个
                    try:
                        file_date = pd.to_datetime(sf.stem)
                        file_size = sf.stat().st_size / 1024  # KB
                        # 尝试读取文件获取记录数
                        try:
                            df = pd.read_csv(sf)
                            record_count = len(df)
                        except:
                            record_count = 0
                        selector_list.append({
                            "日期": file_date.strftime("%Y-%m-%d"),
                            "文件大小": f"{file_size:.1f} KB",
                            "记录数": record_count,
                            "文件路径": str(sf.relative_to(base_path))
                        })
                    except:
                        pass
                
                if selector_list:
                    selector_df = pd.DataFrame(selector_list)
                    st.dataframe(selector_df, hide_index=True, width='stretch')
            else:
                st.info("📝 尚未保存任何选股结果。选股完成后，结果将自动保存到 `data/signals/z_selectors/` 目录。")
        
        # 数据仓库路径提示
        st.caption(f"💾 数据仓库路径: `{base_path.absolute()}`")
        
    except Exception as e:
        st.error(f"获取数据仓库统计信息时出错: {e}")


def save_selector_results(result_df: pd.DataFrame, trade_date: str) -> bool:
    """保存选股结果到本地文件"""
    try:
        from pathlib import Path
        from core.data_store import BASE_DIR
        
        base_path = Path(BASE_DIR)
        signals_dir = base_path / "signals" / "z_selectors"
        signals_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用交易日期作为文件名
        date_str = pd.to_datetime(trade_date).strftime("%Y-%m-%d")
        file_path = signals_dir / f"{date_str}.csv"
        
        # 保存为CSV
        result_df.to_csv(file_path, index=False, encoding='utf-8-sig')
        
        return True
    except Exception as e:
        print(f"保存选股结果失败: {e}")
        return False


def check_authentication() -> bool:
    """检查用户是否已登录，如果未登录则显示登录页面"""
    # ========== 开发调试开关 ==========
    # 设为 True 时跳过所有密码验证，方便开发调试
    # 生产环境请设为 False
    DEBUG_SKIP_AUTH = True
    if DEBUG_SKIP_AUTH:
        return True
    # ==================================
    
    # 动态检查是否启用了登录（支持运行时更新配置）
    login_enabled = is_login_enabled()
    
    # 检查是否首次运行（没有密码配置且没有跳过标记）
    skip_marker = os.path.join(".streamlit", ".skip_password_setup")
    is_first_run = not login_enabled and not os.path.exists(skip_marker)
    
    # 如果是首次运行，显示设置页面
    if is_first_run:
        render_first_time_setup()
        st.stop()  # 阻止继续执行主程序
        return False
    
    # 如果未启用登录，直接返回 True（开发模式）
    if not login_enabled:
        return True
    
    # 检查 session_state 中的认证状态
    if st.session_state.get("authenticated", False):
        return True
    
    # 未登录，显示登录页面
    render_login_page()
    st.stop()  # 阻止继续执行主程序
    return False


# ==================== 主函数 ====================

def main():
    # ========= 登录认证检查（必须在最前面） =========
    if not check_authentication():
        return  # 如果未通过认证，check_authentication 会调用 st.stop()
    
    # Apple Design System - Hero Header
    render_compact_header(
        title="Quant-AI Dashboard",
    )
    
    # ========= 从本地加载用户配置（仅在会话首次运行时） =========
    if "user_state_loaded" not in st.session_state:
        stored_state = load_user_state()
        for k, v in stored_state.items():
            # 只在 session_state 中不存在时写入，避免覆盖当前会话中的临时修改
            if k not in st.session_state:
                st.session_state[k] = v
        st.session_state.user_state_loaded = True

    # ========= 从本地加载模拟账户状态（仅在会话首次运行时） =========
    if "paper_account_loaded" not in st.session_state:
        from core.account import ensure_account_dict

        loaded_account = load_paper_account()
        if loaded_account:
            # 使用 account 模块统一补全结构
            st.session_state.paper_account = ensure_account_dict(
                loaded_account,
                initial_capital=float(loaded_account.get("initial_capital", 1_000_000.0)),
            )
        st.session_state.paper_account_loaded = True
    
    # ========= 资产池与全局资产配置（默认资产 + 自定义资产） =========
    default_universe = [
        "BTC-USD", "ETH-USD",
        "AAPL", "TSLA", "NVDA",
        "159755.SZ", "002611", "006810", "160615", "013281",
    ]
    default_ticker_names = {
        "BTC-USD": "Bitcoin",
        "ETH-USD": "Ethereum",
        "AAPL": "Apple",
        "TSLA": "Tesla",
        "NVDA": "NVIDIA",
        "159755.SZ": "广发新能源车电池ETF",
        "002611": "博时黄金ETF联接C",
        "006810": "泰康港股通中证香港银行投资指数C",
        "160615": "鹏华沪深300ETF联接(LOF)A",
        "013281": "国泰海通30天滚动持有中短债债券A",
    }
    
    # 自定义资产池（用户可添加任意代码）
    if "custom_assets" not in st.session_state:
        # 每项结构: {"ticker": "...", "name": "...", "category": "..."}
        st.session_state.custom_assets = []

    # 用户自定义名称（覆盖默认名称），可作用于任意资产代码
    if "user_ticker_names" not in st.session_state:
        st.session_state.user_ticker_names = {}
    
    custom_tickers = [a["ticker"] for a in st.session_state.custom_assets]
    custom_names = {a["ticker"]: (a.get("name") or a["ticker"]) for a in st.session_state.custom_assets}
    user_ticker_names = st.session_state.user_ticker_names
    
    # 合并预设和自定义资产池，名称优先级：用户自定义 > 自定义资产 > 默认名称
    all_universe = default_universe + [t for t in custom_tickers if t not in default_universe]
    ticker_names = {**default_ticker_names, **custom_names, **user_ticker_names}
    
    # 已选资产列表，初始为一组默认资产
    if "selected_tickers" not in st.session_state:
        st.session_state.selected_tickers = ["159755.SZ", "002611", "006810", "160615", "013281"]
    tickers = st.session_state.selected_tickers
       
    # 侧边栏参数
    st.sidebar.header("参数设置")
    
    st.sidebar.markdown("**历史回看天数**")
    st.sidebar.caption(
        "用于分析的历史数据时间范围，会同时影响收益率计算、风险估计以及预测模型的输入。"
        "在量化交易中，常见的选择包括：60天（约3个月）、120天（约半年）、252天（约1年）。"
    )
    # 允许最长回看约 10 年（3650 天），实际本地缓存会尽量覆盖这一窗口
    days = st.sidebar.slider(
        "历史回看天数（天）",
        60,
        3650,
        252,
        label_visibility="collapsed",
        help="历史窗口越长，估计的波动率和相关性越稳定，但对近期结构变化的反应会变慢；窗口越短，模型对最新行情更敏感，但噪声也更大。"
    )
    
    # 数据源选择
    if "data_sources" not in st.session_state:
        # 默认启用 AkShare + Binance，yfinance/AlphaVantage 可按需勾选
        st.session_state.data_sources = ["AkShare", "Binance"]
    
    # API 密钥优先从环境变量读取，其次允许在界面中输入
    if "alpha_vantage_key" not in st.session_state:
        st.session_state.alpha_vantage_key = DEFAULT_ALPHA_VANTAGE_KEY
    if "tushare_token" not in st.session_state:
        st.session_state.tushare_token = DEFAULT_TUSHARE_TOKEN
    
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    st.sidebar.markdown("**数据源**")
    st.sidebar.caption("选择要使用的数据源（可多选）")
    
    # AkShare 数据源
    use_akshare = st.sidebar.checkbox(
        "AkShare（A股/ETF/基金/部分美股）", 
        value="AkShare" in st.session_state.data_sources,
        help="支持A股、深圳/上海ETF、公募基金及部分美股（AAPL、TSLA、NVDA等）。国内直接可用，无需代理。",
        disabled=not AKSHARE_AVAILABLE
    )
    
    # Binance 数据源（加密货币）
    use_binance = st.sidebar.checkbox(
        "Binance（加密货币）",
        value="Binance" in st.session_state.data_sources,
        help="通过 Binance 公共 API 获取加密货币日线数据，例如 BTC-USD、ETH-USD 等。"
    )
    
    # Alpha Vantage 数据源（美股）
    use_alpha = st.sidebar.checkbox(
        "Alpha Vantage（美股）",
        value="AlphaVantage" in st.session_state.data_sources,
        help="免费 API，用于获取美股日线数据。需要提供 API Key。"
    )
    alpha_key = st.sidebar.text_input(
        "Alpha Vantage API Key",
        value=st.session_state.alpha_vantage_key,
        type="password",
        help="用于请求 Alpha Vantage 的 API Key。免费版有频率限制，适合少量标的的 Demo。",
    )
    st.session_state.alpha_vantage_key = alpha_key.strip()

    # Tushare 数据源（A股/基金）
    use_tushare = st.sidebar.checkbox(
        "Tushare（A股/基金）",
        value="Tushare" in st.session_state.data_sources,
        help="使用 Tushare Pro 获取 A股及部分基金的高质量历史行情数据，需要有效的 Tushare Token。",
    )
    ts_token = st.sidebar.text_input(
        "Tushare API Token",
        value=st.session_state.tushare_token,
        type="password",
        help="用于请求 Tushare Pro 的 Token。建议在本地环境安全保存。",
    )
    st.session_state.tushare_token = ts_token.strip()
    
    # yfinance 数据源（最后兜底）
    use_yfinance = st.sidebar.checkbox(
        "yfinance（美股/加密货币 - 兜底）", 
        value="yfinance" in st.session_state.data_sources,
        help="支持美股（AAPL、TSLA等）、加密货币（BTC-USD、ETH-USD等）。易受限流影响，建议仅作为兜底方案。"
    )
    
    # 更新 session_state
    data_sources = []
    if use_akshare:
        data_sources.append("AkShare")
    if use_binance:
        data_sources.append("Binance")
    if use_alpha and alpha_key.strip():
        data_sources.append("AlphaVantage")
    if use_tushare and ts_token.strip():
        data_sources.append("Tushare")
    if use_yfinance:
        data_sources.append("yfinance")
    st.session_state.data_sources = data_sources
    
    if not data_sources:
        st.sidebar.warning("请至少选择一个数据源")
    
    # 初始化最近数据获取时间
    if "last_data_fetch_time" not in st.session_state:
        st.session_state.last_data_fetch_time = None
    
    # 数据刷新控制（包括缓存与本地仓库）
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    if st.sidebar.button("刷新数据", help="清除缓存并重新从数据源拉取最新数据（包括所有分析结果）", key="refresh_data_btn"):
        st.cache_data.clear()
        # 使用 session_state 标记需要刷新，而不是立即 rerun
        st.session_state.data_refreshed = True
        st.success("数据已刷新，请重新选择资产或刷新页面查看最新数据")

    # 手动/自动更新本地数据仓库（阶段 2：简易触发 + 伪定时）
    # 提示：在“后台服务”标签页中，推荐使用独立进程运行 core.daemon 作为长期数据更新入口；
    # 这里的自动更新仅在当前浏览器会话存活期间生效，适合作为本机临时调试补充。
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    st.sidebar.markdown("**本地数据仓库更新**")

    # 自动更新配置保存在 session_state 中
    if "auto_update_local" not in st.session_state:
        st.session_state.auto_update_local = False
    if "auto_update_interval_min" not in st.session_state:
        st.session_state.auto_update_interval_min = 60
    if "last_auto_update_time" not in st.session_state:
        st.session_state.last_auto_update_time = None

    auto_col1, auto_col2 = st.sidebar.columns([1, 1])
    with auto_col1:
        st.session_state.auto_update_local = st.checkbox(
            "自动更新",
            value=st.session_state.auto_update_local,
            help="在本会话内，按设定间隔自动尝试更新本地仓库（基于应用重新运行触发）。",
        )
    with auto_col2:
        st.session_state.auto_update_interval_min = st.selectbox(
            "频率(分钟)",
            options=[15, 30, 60, 120, 240],
            index=[15, 30, 60, 120, 240].index(st.session_state.auto_update_interval_min)
            if st.session_state.auto_update_interval_min in [15, 30, 60, 120, 240]
            else 2,
        )

    # 手动立即更新按钮
    if st.sidebar.button("立即更新本地数据", help="为当前选中的资产从远程数据源拉取最新日线数据，并写入本地 Parquet 仓库。"):
        try:
            from core.data_updater import update_local_history_for_tickers

            with st.spinner("正在更新本地数据仓库..."):
                update_local_history_for_tickers(
                    tickers=tickers,
                    days=days,
                    data_sources=data_sources,
                    alpha_vantage_key=st.session_state.alpha_vantage_key if "alpha_vantage_key" in st.session_state else None,
                    tushare_token=st.session_state.tushare_token if "tushare_token" in st.session_state else None,
                )
            st.session_state.last_auto_update_time = datetime.now()
            st.success("本地数据仓库更新完成。后续分析将优先使用本地缓存，加快加载速度。")
        except Exception as e:
            st.error(f"更新本地数据仓库时出错：{e}")

    # 伪定时自动更新：在每次脚本运行时检查是否到达间隔
    if st.session_state.auto_update_local and tickers:
        from datetime import timedelta

        now = datetime.now()
        last_time = st.session_state.last_auto_update_time
        interval = timedelta(minutes=st.session_state.auto_update_interval_min)
        if last_time is None or (now - last_time) >= interval:
            try:
                from core.data_updater import update_local_history_for_tickers

                with st.spinner("自动更新本地数据仓库中..."):
                    update_local_history_for_tickers(
                        tickers=tickers,
                        days=days,
                        data_sources=data_sources,
                        alpha_vantage_key=st.session_state.alpha_vantage_key if "alpha_vantage_key" in st.session_state else None,
                        tushare_token=st.session_state.tushare_token if "tushare_token" in st.session_state else None,
                    )
                st.session_state.last_auto_update_time = now
                st.sidebar.success("已完成一次自动更新本地数据。")
            except Exception as e:
                st.sidebar.error(f"自动更新本地数据仓库时出错：{e}")
    
    # 侧边栏分隔线（精简样式）
    st.sidebar.markdown("---")

        # ========= 侧边栏：登录状态与登出 =========
    if is_login_enabled():
        st.sidebar.markdown("---")
        st.sidebar.markdown("账户")
        if st.session_state.get("authenticated", False):
            st.sidebar.success("已登录")
            if st.sidebar.button("登出", width='stretch', type="secondary"):
                st.session_state["authenticated"] = False
                st.rerun()
        st.sidebar.markdown("---")
    
    # 显示版本号（在侧边栏底部）
    st.sidebar.markdown("---")
    version_info = get_version_info()
    st.sidebar.caption(f"版本 v{VERSION}")
    st.sidebar.caption(f"构建日期: {version_info.get('build_date', 'N/A')}")
    
    if not tickers:
        st.warning("请在左侧选择至少一个资产。")
        return
    
    # 检查数据源是否已选择
    if not data_sources:
        st.error("请在左侧选择至少一个数据源")
        st.stop()
    
    # 加载数据（通过统一数据服务，优先本地缓存）
    with st.status("正在加载数据...", expanded=False) as status:
        st.write(f"📊 正在从数据源获取 {len(tickers)} 个资产的数据...")
        st.write(f"📅 历史回看天数: {days} 天")
        st.write(f"🔌 数据源: {', '.join(data_sources)}")
        try:
            data = load_price_data(
                tickers,
                days,
                data_sources=data_sources,
                alpha_vantage_key=st.session_state.alpha_vantage_key if "alpha_vantage_key" in st.session_state else None,
                tushare_token=st.session_state.tushare_token if "tushare_token" in st.session_state else None,
            )
            if data.empty:
                status.update(label="数据加载失败", state="error")
                st.error("获取的数据为空，请检查资产代码是否正确或稍后重试。")
                st.stop()
            else:
                status.update(label=f"数据加载完成！成功获取 {len(data.columns)} 个资产的数据", state="complete")
        except ValueError as e:
            error_msg = str(e)
            if "限流" in error_msg or "Rate" in error_msg or "Too Many" in error_msg:
                show_rate_limit_error("yfinance")
                st.stop()
            elif "代理" in error_msg or "连接失败" in error_msg:
                show_network_error(error_msg)
                st.info("""
                **特别提示：**
                - 国内网络无法直接访问 Yahoo Finance
                - 建议只勾选"AkShare"数据源，仅分析A股/ETF/基金
                - 如需美股/加密货币数据，请配置网络代理
                """)
                st.stop()
            else:
                show_data_fetch_error(error_msg, ", ".join(data_sources))
                st.stop()
        except Exception as e:
            show_data_fetch_error(str(e), ", ".join(data_sources))
            st.stop()
    
    # 将数据存储到 session_state，供页面模块使用
    st.session_state.data = data
    st.session_state.tickers = tickers
    st.session_state.ticker_names = ticker_names
    
    # 记录最近一次成功获取数据的时间
    st.session_state.last_data_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 确保索引是日期类型
    if not isinstance(data.index, pd.DatetimeIndex):
        try:
            data.index = pd.to_datetime(data.index)
        except:
            pass
    
    # 过滤掉无法获取数据的ticker，只保留实际有数据的ticker（仅影响本次分析，不改变用户资产池选择）
    available_tickers = [t for t in tickers if t in data.columns]
    if len(available_tickers) < len(tickers):
        missing_tickers = [t for t in tickers if t not in data.columns]
        if missing_tickers:
            st.warning(f"以下资产本次未能成功获取数据，已在当前分析中暂时忽略：{', '.join(missing_tickers)}")
            st.info("提示：请检查资产代码是否正确，或确认该资产是否受当前选择的数据源支持。A股/ETF/基金需要 AkShare，美股/加密货币需要 yfinance（国内可能需要代理）。")
    tickers = available_tickers
    
    if not tickers:
        st.error("没有可用的资产数据，请检查资产代码或使用模拟数据。")
        st.stop()
    
    # 数据质量检查
    if "show_data_quality" not in st.session_state:
        st.session_state.show_data_quality = False
    
    quality_reports = safe_execute(
        lambda: DataQualityChecker.check_dataframe_quality(data, tickers),
        default_return={},
        error_message="数据质量检查失败"
    )
    
    # 如果有质量问题，显示警告
    if quality_reports:
        quality_issues = [r for r in quality_reports.values() if r.level in [QualityLevel.WARNING, QualityLevel.ERROR]]
        if quality_issues:
            with st.expander("⚠️ 数据质量警告", expanded=False):
                for report in quality_issues:
                    st.markdown(f"**{report.ticker}** - {report.level.value} (得分: {report.score:.1f}/100)")
                    if report.issues:
                        for issue in report.issues:
                            st.caption(f"  • {issue}")
                    if report.recommendations:
                        st.info("建议: " + "; ".join(report.recommendations))
    
    # 创建标签页 - Apple风格（默认进入概览页面）
    st.markdown("<br>", unsafe_allow_html=True)
    from core.strategy_engine import generate_multi_asset_signals, _interpret_action

    # ==================== 标签页布局 ====================
    # 按使用流程分组：核心分析 → 策略选股 → 深度分析 → 策略验证 → 管理配置 → 后台服务
    tab_overview, tab_select, tab_ai, tab_signals, tab_tech, tab_risk, tab_risk_mgmt, tab_corr, tab_bt, tab_pool, tab_account, tab_monitoring, tab_daemon = st.tabs(
        [
            "概览",
            "选股",
            "AI预测",
            "交易信号",
            "技术指标",
            "风险分析",
            "风险管理",
            "相关性",
            "回测",
            "资产池",
            "模拟账户",
            "系统监控",
            "后台服务",
        ]
    )
    
    # 计算收益率（多个标签页共用）- 使用缓存
    log_ret = calculate_returns_cached(data)
    
    # ==================== 标签页: 概览 ====================
    with tab_overview:
        from core.page_modules.overview import render_overview_page
        render_overview_page()
    
    # ==================== 标签页: 资产池 ====================
    with tab_pool:
        from core.page_modules.asset_pool import render_asset_pool_page
        render_asset_pool_page(default_universe, ticker_names)
    
    # ==================== 标签页: 选股（StockTradebyZ 战法） ====================
    with tab_select:
        from core.page_modules.stock_selection import render_stock_selection_page
        render_stock_selection_page()

    # ==================== 标签页: AI预测 ====================
    with tab_ai:
        from core.page_modules.ai_forecast import render_ai_forecast_page
        render_ai_forecast_page()

    # ==================== 标签页: 交易信号 ====================
    with tab_signals:
        from core.page_modules.trading_signals import render_trading_signals_page
        render_trading_signals_page()

    # ==================== 标签页: 模拟账户 ====================
    with tab_account:
        from core.page_modules.paper_account import render_paper_account_page
        render_paper_account_page()

    # ==================== 标签页: 系统监控 ====================
    with tab_monitoring:
        from core.page_modules.system_monitoring import render_system_monitoring_page
        render_system_monitoring_page()

    # ==================== 标签页: 后台服务（Daemon） ====================
    with tab_daemon:
        from core.page_modules.daemon import render_daemon_page
        render_daemon_page()

    # ==================== 标签页: 技术指标 ====================
    with tab_tech:
        from core.page_modules.technical_indicators import render_technical_indicators_page
        render_technical_indicators_page()

    # ==================== 标签页: 风险分析 ====================
    with tab_risk:
        from core.page_modules.risk_analysis import render_risk_analysis_page
        render_risk_analysis_page()

    # ==================== 标签页: 风险管理 ====================
    with tab_risk_mgmt:
        from core.page_modules.risk_management import render_risk_management_page
        render_risk_management_page()

    # ==================== 标签页: 相关性分析 ====================
    with tab_corr:
        from core.page_modules.correlation import render_correlation_page
        render_correlation_page()

    # ==================== 标签页: 回测 ====================
    with tab_bt:
        from core.page_modules.backtest import render_backtest_page
        render_backtest_page()

    # 在页面结束前持久化一次用户状态（资产池、数据源、API Key 等）以及模拟账户
    save_user_state()
    save_paper_account()
    
    # 精简页脚
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown(f"""
    <div style='text-align: center; padding: 0.75rem 0 1rem 0; color: #A0A0A5; font-size: 0.8rem;'>
        <span>Quant-AI Dashboard v{VERSION} · by Francesco</span>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
