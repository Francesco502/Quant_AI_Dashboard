"""
用户友好的错误提示UI组件
提供统一的错误展示格式和操作建议
"""
import streamlit as st
from typing import List, Optional


def show_user_friendly_error(
    error_type: str,
    title: str = None,
    message: str = None,
    details: str = None,
    suggestions: List[str] = None,
    actions: List[dict] = None,
):
    """
    显示用户友好的错误提示
    
    Args:
        error_type: 错误类型（data_fetch, network, validation, calculation等）
        title: 错误标题（如果为None，则使用默认标题）
        message: 错误消息
        details: 详细错误信息（可选）
        suggestions: 建议操作列表
        actions: 操作按钮列表，格式：[{"label": "按钮文本", "key": "按钮key"}]
    """
    # 错误类型模板
    error_templates = {
        "data_fetch": {
            "title": "📊 数据获取失败",
            "icon": "📊",
            "default_message": "无法获取资产数据，请检查以下内容：",
            "default_suggestions": [
                "检查网络连接是否正常",
                "确认资产代码格式正确（如：600519.SS、AAPL、BTC-USD）",
                "尝试更换数据源（A股使用AkShare，美股使用yfinance）",
                "检查API密钥是否有效（如使用AlphaVantage或Tushare）"
            ]
        },
        "network": {
            "title": "🌐 网络连接问题",
            "icon": "🌐",
            "default_message": "网络连接出现问题：",
            "default_suggestions": [
                "检查网络连接是否正常",
                "如果使用代理，请确认代理配置正确",
                "尝试刷新页面重试",
                "检查防火墙设置"
            ]
        },
        "validation": {
            "title": "⚠️ 数据验证失败",
            "icon": "⚠️",
            "default_message": "输入数据不符合要求：",
            "default_suggestions": [
                "检查输入的数据格式是否正确",
                "确认必填字段已填写",
                "检查数值范围是否合理"
            ]
        },
        "calculation": {
            "title": "🔢 计算错误",
            "icon": "🔢",
            "default_message": "计算过程中出现错误：",
            "default_suggestions": [
                "检查输入数据是否完整",
                "确认数据质量是否满足计算要求",
                "尝试减少数据量或调整参数"
            ]
        },
        "rate_limit": {
            "title": "⏱️ 请求频率限制",
            "icon": "⏱️",
            "default_message": "请求过于频繁，已达到速率限制：",
            "default_suggestions": [
                "等待 5-10 分钟后再试",
                "减少选择的资产数量（一次只选 1-2 个）",
                "使用本地数据缓存功能",
                "考虑升级API套餐（如使用付费数据源）"
            ]
        },
        "permission": {
            "title": "🔒 权限不足",
            "icon": "🔒",
            "default_message": "当前操作需要相应权限：",
            "default_suggestions": [
                "检查是否已登录",
                "确认账户权限是否足够",
                "联系管理员获取相应权限"
            ]
        }
    }
    
    # 获取错误模板
    template = error_templates.get(error_type, {
        "title": "❌ 发生错误",
        "icon": "❌",
        "default_message": "操作失败：",
        "default_suggestions": ["请稍后重试", "如问题持续，请联系技术支持"]
    })
    
    # 使用自定义标题或默认标题
    display_title = title or template["title"]
    display_message = message or template["default_message"]
    
    # 显示错误容器
    with st.container():
        st.error(f"**{display_title}**")
        
        if display_message:
            st.markdown(display_message)
        
        # 显示详细错误信息（如果有）
        if details:
            with st.expander("🔍 详细错误信息", expanded=False):
                st.code(details, language=None)
        
        # 显示建议操作
        if suggestions or template.get("default_suggestions"):
            st.markdown("**💡 建议操作：**")
            suggestion_list = suggestions or template["default_suggestions"]
            for i, suggestion in enumerate(suggestion_list, 1):
                st.markdown(f"{i}. {suggestion}")
        
        # 显示操作按钮（如果有）
        if actions:
            st.markdown("**🔧 快速操作：**")
            cols = st.columns(len(actions))
            for i, action in enumerate(actions):
                with cols[i]:
                    if st.button(action.get("label", "操作"), key=action.get("key", f"action_{i}")):
                        if "callback" in action:
                            action["callback"]()


def show_data_fetch_error(error_details: str = None, data_source: str = None):
    """显示数据获取错误的快捷方法"""
    suggestions = [
        "检查网络连接是否正常",
        "确认资产代码格式正确",
        "尝试更换数据源"
    ]
    
    if data_source:
        if "yfinance" in data_source:
            suggestions.append("yfinance需要代理访问，请配置代理或使用其他数据源")
        elif "Tushare" in data_source:
            suggestions.append("请检查Tushare Token是否有效")
        elif "AlphaVantage" in data_source:
            suggestions.append("请检查AlphaVantage API Key是否有效")
    
    show_user_friendly_error(
        error_type="data_fetch",
        details=error_details,
        suggestions=suggestions,
        actions=[
            {
                "label": "🔄 刷新数据",
                "key": "refresh_data",
                "callback": lambda: st.rerun()
            }
        ]
    )


def show_rate_limit_error(service_name: str = "数据服务"):
    """显示速率限制错误的快捷方法"""
    show_user_friendly_error(
        error_type="rate_limit",
        message=f"{service_name} 有请求频率限制",
        suggestions=[
            f"等待 5-10 分钟后再试（{service_name} 有请求频率限制）",
            "减少选择的资产数量（一次只选 1-2 个）",
            "点击左侧'刷新数据'按钮重试"
        ]
    )


def show_network_error(error_details: str = None):
    """显示网络错误的快捷方法"""
    show_user_friendly_error(
        error_type="network",
        details=error_details,
        suggestions=[
            "检查网络连接是否正常",
            "如果使用代理，请确认代理配置正确",
            "尝试刷新页面重试"
        ]
    )

