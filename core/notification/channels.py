"""各推送渠道实现：企微、飞书、钉钉、邮件、Telegram、Pushover。"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _post(url: str, json: Dict[str, Any], timeout: int = 10) -> bool:
    try:
        import requests

        r = requests.post(url, json=json, timeout=timeout)
        r.raise_for_status()
        return True
    except Exception as e:
        logger.warning("POST %s 失败: %s", url[:50], e)
        return False


def _send_wechat(webhook_url: str, title: str, body_md: str) -> bool:
    """企业微信机器人 Webhook（支持 markdown）"""
    payload = {
        "msgtype": "markdown",
        "markdown": {"content": f"**{title}**\n\n{body_md}"},
    }
    return _post(webhook_url, payload)


def _send_feishu(webhook_url: str, title: str, body_md: str) -> bool:
    """飞书机器人 Webhook（使用 text 或 markdown 视版本）"""
    payload = {
        "msg_type": "text",
        "content": {"text": f"{title}\n\n{body_md}"},
    }
    return _post(webhook_url, payload)


def _send_dingtalk(webhook_url: str, title: str, body_md: str) -> bool:
    """钉钉机器人 Webhook（markdown 类型）"""
    payload = {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": body_md},
    }
    return _post(webhook_url, payload)


def _send_telegram(bot_token: str, chat_id: str, title: str, body_md: str) -> bool:
    """Telegram sendMessage（Markdown）"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    text = f"*{title}*\n\n{body_md}"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    return _post(url, payload)


def _send_email(title: str, body_md: str) -> bool:
    """邮件（从环境变量读取 SMTP 与收件人）"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    user = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    receivers = os.getenv("EMAIL_RECEIVERS", "").strip() or (user or "")
    if not user or not password or not receivers:
        return False
    to_list = [r.strip() for r in receivers.split(",") if r.strip()]
    try:
        msg = MIMEMultipart()
        msg["From"] = user
        msg["To"] = ", ".join(to_list)
        msg["Subject"] = title
        msg.attach(MIMEText(body_md, "plain", "utf-8"))
        with smtplib.SMTP(os.getenv("SMTP_SERVER", "smtp.qq.com"), int(os.getenv("SMTP_PORT", "587"))) as s:
            s.starttls()
            s.login(user, password)
            s.sendmail(user, to_list, msg.as_string())
        return True
    except Exception as e:
        logger.warning("邮件发送失败: %s", e)
        return False


def _send_pushover(title: str, body_md: str) -> bool:
    """Pushover API"""
    token = os.getenv("PUSHPLUS_TOKEN")  # 国内常用 PushPlus，接口类似
    if not token:
        token = os.getenv("PUSHOVER_TOKEN")
    if not token:
        return False
    # PushPlus 简单推送
    url = "https://www.pushplus.plus/send"
    payload = {"token": token, "title": title, "content": body_md}
    return _post(url, payload)


def send_to_all_configured_channels(
    title: str,
    body_md: str,
    *,
    channels_filter: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """向所有已配置的渠道发送同一标题与正文。

    Returns:
        {"sent": ["wechat", ...], "failed": ["dingtalk"], "errors": {"dingtalk": "..."}}
    """
    sent: List[str] = []
    failed: List[str] = []
    errors: Dict[str, str] = {}

    def try_channel(name: str, fn) -> None:
        if channels_filter is not None and name not in channels_filter:
            return
        try:
            if fn():
                sent.append(name)
            else:
                failed.append(name)
        except Exception as e:
            failed.append(name)
            errors[name] = str(e)

    wechat_url = os.getenv("WECHAT_WEBHOOK_URL")
    if wechat_url:
        try_channel("wechat", lambda: _send_wechat(wechat_url, title, body_md))

    feishu_url = os.getenv("FEISHU_WEBHOOK_URL")
    if feishu_url:
        try_channel("feishu", lambda: _send_feishu(feishu_url, title, body_md))

    dingtalk_url = os.getenv("DINGTALK_WEBHOOK_URL")
    if dingtalk_url:
        try_channel("dingtalk", lambda: _send_dingtalk(dingtalk_url, title, body_md))

    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat = os.getenv("TELEGRAM_CHAT_ID")
    if telegram_token and telegram_chat:
        try_channel(
            "telegram",
            lambda: _send_telegram(telegram_token, telegram_chat, title, body_md),
        )

    if os.getenv("EMAIL_SENDER") and os.getenv("EMAIL_PASSWORD"):
        try_channel("email", lambda: _send_email(title, body_md))

    if os.getenv("PUSHPLUS_TOKEN") or os.getenv("PUSHOVER_TOKEN"):
        try_channel("pushover", lambda: _send_pushover(title, body_md))

    return {"sent": sent, "failed": failed, "errors": errors}
