"""决策报告 / 复盘报告推送模块（daily_stock_analysis 移植）

职责：
- 将决策仪表盘、大盘复盘等内容格式化为 Markdown/卡片；
- 通过企微、飞书、钉钉、邮件、Telegram、Pushover 等渠道发送；
- 对外统一接口：send_report(report_type, content_dict)。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .formatter import format_dashboard_report, format_market_review_report
from .channels import send_to_all_configured_channels

logger = logging.getLogger(__name__)

ReportType = str  # "dashboard" | "market_review"


def send_report(
    report_type: str,
    content: Dict[str, Any],
    *,
    channels_filter: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """发送报告到已配置的推送渠道。

    Args:
        report_type: "dashboard" 决策仪表盘 | "market_review" 大盘复盘
        content: 与 report_type 对应的结构化内容（与 API 返回格式一致）
        channels_filter: 仅使用这些渠道，如 ["wechat","feishu"]；None 表示使用全部已配置渠道

    Returns:
        {"sent": ["wechat","feishu"], "failed": ["dingtalk"], "errors": {"dingtalk": "..."}}
    """
    if report_type == "dashboard":
        title, body_md = format_dashboard_report(content)
    elif report_type == "market_review":
        title, body_md = format_market_review_report(content)
    else:
        logger.warning("未知 report_type=%s，跳过推送", report_type)
        return {"sent": [], "failed": [], "errors": {}}

    return send_to_all_configured_channels(
        title=title,
        body_md=body_md,
        channels_filter=channels_filter,
    )
