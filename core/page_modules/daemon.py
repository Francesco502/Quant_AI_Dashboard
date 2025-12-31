"""
后台服务（Daemon）管理页面模块
"""
import streamlit as st
import json
import os
import time
import subprocess
import sys
import platform
from pathlib import Path


def render_daemon_page():
    """渲染后台服务管理页面"""
    st.markdown("### 后台服务（Daemon）管理")
    st.caption(
        "管理后台守护进程：配置任务参数、启动/停止服务、查看运行状态和日志。"
        "也可以通过终端执行 `python -m core.daemon` 手动启动。"
    )

    # 为避免循环导入，仅在此处延迟导入路径常量
    try:
        from core import daemon as core_daemon

        config_path = core_daemon.CONFIG_PATH
        status_path = core_daemon.STATUS_PATH
    except Exception:
        # 回退到相对路径推断
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "daemon_config.json")
        status_path = os.path.join(base_dir, "daemon_status.json")

    col_cfg, col_status = st.columns([1.2, 1])

    # -------- 配置编辑面板 --------
    with col_cfg:
        st.markdown("#### 配置（daemon_config.json）")
        st.caption("通过修改下方表单来调整后台服务的标的池、更新频率、交易开关等。")

        # 读取现有配置，如不存在则调用 core.daemon 的默认生成逻辑
        cfg: dict
        try:
            from core.daemon import load_config as _daemon_load_config

            cfg = _daemon_load_config()
        except Exception:
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                except Exception:
                    cfg = {}
            else:
                cfg = {}

        st.write("当前配置文件路径：", f"`{os.path.relpath(config_path, os.path.dirname(__file__))}`")

        # 基础参数
        universe = st.text_area(
            "标的池（逗号分隔）",
            value=",".join(cfg.get("universe", [])),
            help="例如：159755.SZ,002611,006810,160615,013281",
        )
        days_cfg = st.number_input(
            "历史窗口天数",
            min_value=60,
            max_value=3650,
            value=int(cfg.get("days", 365)),
            step=30,
        )

        ds_default = cfg.get("data_sources") or ["AkShare", "Tushare"]
        data_sources = st.multiselect(
            "数据源",
            options=["AkShare", "Tushare", "yfinance"],
            default=ds_default,
        )

        st.markdown("##### 数据更新任务")
        du = cfg.get("data_update", {}) or {}
        du_enabled = st.checkbox("启用数据更新任务", value=bool(du.get("enabled", True)))
        du_time = st.text_input(
            "每日固定时间（可选，格式 HH:MM，例如 23:30）",
            value=str(du.get("time", "")),
        )
        du_interval = st.number_input(
            "或按固定间隔分钟运行（留空代表不使用该模式）",
            min_value=1,
            max_value=24 * 60,
            value=int(du.get("interval_minutes", 60)),
            step=5,
            key="data_update_interval_minutes",
        )

        st.markdown("##### 模拟交易任务")
        tr = cfg.get("trading", {}) or {}
        tr_enabled = st.checkbox("启用模拟交易任务", value=bool(tr.get("enabled", False)))
        tr_time = st.text_input(
            "每日固定时间（可选，格式 HH:MM，例如 09:20）",
            value=str(tr.get("time", "")),
        )
        tr_interval = st.number_input(
            "或按固定间隔分钟运行（留空代表不使用该模式）",
            min_value=1,
            max_value=24 * 60,
            value=int(tr.get("interval_minutes", 60)),
            step=5,
            key="trading_interval_minutes",
        )
        tr_max_positions = st.number_input(
            "最大持仓数",
            min_value=1,
            max_value=50,
            value=int(tr.get("max_positions", 5)),
            step=1,
        )
        tr_initial_capital = st.number_input(
            "初始资金（元）",
            min_value=1_000.0,
            max_value=100_000_000.0,
            value=float(tr.get("initial_capital", 1_000_000.0)),
            step=100_000.0,
            format="%.0f",
        )

        if st.button("保存后台服务配置", type="primary"):
            try:
                new_cfg = {
                    "universe": [t.strip() for t in universe.split(",") if t.strip()],
                    "days": int(days_cfg),
                    "data_sources": data_sources,
                    "alpha_vantage_key": cfg.get("alpha_vantage_key", ""),
                    "tushare_token": cfg.get("tushare_token", ""),
                    "data_update": {
                        "enabled": du_enabled,
                        "time": du_time.strip() or None,
                        "interval_minutes": int(du_interval) if du_interval else None,
                    },
                    "trading": {
                        "enabled": tr_enabled,
                        "time": tr_time.strip() or None,
                        "interval_minutes": int(tr_interval) if tr_interval else None,
                        "max_positions": int(tr_max_positions),
                        "initial_capital": float(tr_initial_capital),
                    },
                }
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(new_cfg, f, ensure_ascii=False, indent=2)
                st.success("后台服务配置已保存。新的配置将在下次启动或下一轮任务时生效。")
            except Exception as e:
                st.error(f"保存配置时出错：{e}")

    # -------- 状态查看面板 --------
    with col_status:
        st.markdown("#### 运行状态（daemon_status.json）")
        st.caption("后台守护进程会在每次任务执行后写入最近一次数据更新与交易时间等信息。")

        # 获取基础目录和 PID 文件路径
        try:
            from core import daemon as core_daemon
            base_dir = os.path.dirname(os.path.dirname(core_daemon.__file__))
        except Exception:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        pid_file = os.path.join(base_dir, "logs", "daemon.pid")
        
        # 检查进程是否运行
        def is_daemon_running():
            """检查后台服务是否正在运行"""
            if not os.path.exists(pid_file):
                return False, None
            
            try:
                with open(pid_file, "r", encoding="utf-8") as f:
                    pid = int(f.read().strip())
                
                # 检查进程是否存在
                if platform.system() == "Windows":
                    # Windows 上使用 tasklist 检查
                    try:
                        result = subprocess.run(
                            ["tasklist", "/FI", f"PID eq {pid}"],
                            capture_output=True,
                            text=True,
                            timeout=2
                        )
                        return str(pid) in result.stdout, pid
                    except:
                        return False, pid
                else:
                    # Linux/Mac 上使用 os.kill 检查
                    try:
                        os.kill(pid, 0)  # 发送信号 0 检查进程是否存在
                        return True, pid
                    except OSError:
                        return False, pid
            except (ValueError, FileNotFoundError):
                return False, None
        
        is_running, daemon_pid = is_daemon_running()
        
        # 进程控制按钮
        st.markdown("##### 进程控制")
        col_start, col_stop = st.columns(2)
        
        with col_start:
            if st.button("启动后台服务", type="primary", disabled=is_running, key="start_daemon_btn"):
                try:
                    # 确保日志目录存在
                    log_dir = os.path.join(base_dir, "logs")
                    os.makedirs(log_dir, exist_ok=True)
                    
                    # 构建启动命令
                    python_exe = sys.executable
                    daemon_module = "core.daemon"
                    
                    # 根据操作系统选择启动方式
                    if platform.system() == "Windows":
                        # Windows: 后台运行
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        startupinfo.wShowWindow = subprocess.SW_HIDE
                        
                        # 启动进程（daemon 会自己创建 PID 文件）
                        process = subprocess.Popen(
                            [python_exe, "-m", daemon_module],
                            cwd=base_dir,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            startupinfo=startupinfo,
                            creationflags=subprocess.CREATE_NO_WINDOW
                        )
                    else:
                        # Linux/Mac: 后台运行
                        process = subprocess.Popen(
                            [python_exe, "-m", daemon_module],
                            cwd=base_dir,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            start_new_session=True
                        )
                    
                    # 等待 daemon 启动并创建 PID 文件（最多等待 3 秒）
                    max_wait = 3
                    waited = 0
                    while waited < max_wait and not os.path.exists(pid_file):
                        time.sleep(0.5)
                        waited += 0.5
                    
                    if os.path.exists(pid_file):
                        try:
                            with open(pid_file, "r", encoding="utf-8") as f:
                                actual_pid = f.read().strip()
                            st.success(f"后台服务已启动（PID: {actual_pid}）")
                        except:
                            st.success(f"后台服务启动中（启动进程 PID: {process.pid}）")
                    else:
                        st.warning(f"后台服务启动中，但尚未检测到 PID 文件（启动进程 PID: {process.pid}）。请稍后刷新页面查看状态。")
                    
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"启动后台服务失败：{e}")
        
        with col_stop:
            if st.button("停止后台服务", disabled=not is_running, key="stop_daemon_btn"):
                if daemon_pid:
                    try:
                        if platform.system() == "Windows":
                            # Windows: 使用 taskkill
                            subprocess.run(
                                ["taskkill", "/F", "/PID", str(daemon_pid)],
                                capture_output=True,
                                timeout=5
                            )
                        else:
                            # Linux/Mac: 使用 kill
                            os.kill(daemon_pid, 15)  # SIGTERM
                            time.sleep(1)
                            try:
                                os.kill(daemon_pid, 0)  # 检查是否还在运行
                                os.kill(daemon_pid, 9)  # 强制杀死
                            except OSError:
                                pass
                        
                        # 删除 PID 文件
                        if os.path.exists(pid_file):
                            os.remove(pid_file)
                        
                        st.success("后台服务已停止")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"停止后台服务失败：{e}")
        
        # 显示进程状态
        if is_running:
            st.success(f"✅ 后台服务正在运行（PID: {daemon_pid}）")
        else:
            st.info("⏸️ 后台服务未运行")
        
        st.markdown("---")
        st.write("当前状态文件路径：", f"`{os.path.relpath(status_path, os.path.dirname(__file__))}`")

        if os.path.exists(status_path):
            try:
                with open(status_path, "r", encoding="utf-8") as f:
                    status = json.load(f)
            except Exception as e:
                st.error(f"读取状态文件失败：{e}")
                status = None
        else:
            status = None

        if not status:
            st.info("尚未检测到状态文件。后台服务启动并执行任务后，状态信息将显示在这里。")
        else:
            last_data = status.get("last_data_update", "未知")
            last_trading = status.get("last_trading_run", "未知")
            last_updated_at = status.get("last_updated_at", "未知")

            st.metric("最近数据更新时间", last_data)
            st.metric("最近交易任务时间", last_trading)
            st.caption(f"状态最后写入时间：{last_updated_at}")

            with st.expander("查看原始状态 JSON"):
                st.json(status)

    # -------- 日志查看面板（新增） --------
    st.markdown("---")
    st.markdown("#### 日志查看")
    st.caption("查看后台守护进程的运行日志，用于排查问题和监控运行状态。")

    # 获取日志文件路径
    try:
        from core import daemon as core_daemon
        base_dir = os.path.dirname(os.path.dirname(core_daemon.__file__))
    except Exception:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    log_dir = os.path.join(base_dir, "logs")
    daemon_log_path = os.path.join(log_dir, "daemon.log")

    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)
    
    # 如果 daemon.log 不存在，创建一个空文件
    if not os.path.exists(daemon_log_path):
        try:
            with open(daemon_log_path, 'w', encoding='utf-8') as f:
                f.write("")
        except Exception as e:
            st.warning(f"无法创建日志文件：{e}")

    # 日志文件选择
    log_files = []
    if os.path.exists(log_dir):
        log_files = [f for f in os.listdir(log_dir) if f.endswith('.log')]
    
    if log_files:
        selected_log = st.selectbox(
            "选择日志文件",
            options=log_files,
            index=0 if "daemon.log" in log_files else 0,
            help="选择要查看的日志文件"
        )
        log_path = os.path.join(log_dir, selected_log)
    else:
        log_path = daemon_log_path
        st.info("logs 目录中暂无日志文件。")

    # 日志显示选项
    col_log1, col_log2 = st.columns([1, 1])
    with col_log1:
        max_lines = st.number_input(
            "显示最近 N 行",
            min_value=50,
            max_value=5000,
            value=500,
            step=50,
            help="只显示日志文件的最后 N 行，避免加载过大文件"
        )
    with col_log2:
        auto_refresh = st.checkbox("自动刷新（每 10 秒）", value=False)

    # 读取并显示日志
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            
            if len(lines) == 0 or (len(lines) == 1 and lines[0].strip() == ""):
                st.info("日志文件为空。后台服务启动并执行任务后，日志内容将显示在这里。")
            else:
                if len(lines) > max_lines:
                    lines = lines[-max_lines:]
                    st.caption(f"显示最后 {max_lines} 行（共 {len(lines)} 行）")
                
                log_content = "".join(lines)
                
                # 使用代码块显示日志
                st.code(log_content, language=None)
            
            # 自动刷新逻辑（使用状态标记，避免页面跳转）
            if auto_refresh:
                # 使用 placeholder 显示倒计时，避免立即 rerun
                countdown_placeholder = st.empty()
                for i in range(10, 0, -1):
                    countdown_placeholder.info(f"⏱️ {i} 秒后自动刷新日志...")
                    time.sleep(1)
                # 仅在日志页面时刷新，使用状态标记
                if "daemon_log_auto_refresh" not in st.session_state:
                    st.session_state.daemon_log_auto_refresh = True
                else:
                    # 清除标记并重新读取日志
                    del st.session_state.daemon_log_auto_refresh
                st.rerun()
                
        except Exception as e:
            st.error(f"读取日志文件失败：{e}")
    else:
        # 如果文件仍然不存在（可能是权限问题），显示提示信息
        st.warning(f"日志文件不存在：{log_path}")
        st.info("""
        **提示：**
        - 如果后台服务正在运行，日志文件会在首次任务执行后自动创建
        - 在 Docker 环境中，确保 logs 目录已正确挂载为 volume
        - 日志文件路径：`logs/daemon.log`
        - 如果问题持续存在，请检查文件系统权限
        """)

