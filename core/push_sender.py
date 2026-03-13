"""多渠道推送模块

借鉴来源: daily_stock_analysis 项目的推送功能

功能：
- 企业微信推送
- 飞书推送
- Telegram推送
- 邮件推送
"""

from __future__ import annotations

import requests
import smtplib
from typing import Dict, List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

from core.llm_client import chat_completion


logger = logging.getLogger(__name__)


class PushSender:
    """推送发送器"""

    @staticmethod
    def send_wechat_webhook(webhook_url: str, title: str, content: str) -> bool:
        """
        企业微信推送

        Args:
            webhook_url: 企业微信Webhook URL
            title: 标题
            content: 内容

        Returns:
            是否推送成功
        """
        try:
            message = {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"### {title}\n\n{content}"
                }
            }
            response = requests.post(webhook_url, json=message, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"企业微信推送失败: {e}")
            return False

    @staticmethod
    def send_feishu_webhook(webhook_url: str, title: str, content: str) -> bool:
        """
        飞书推送

        Args:
            webhook_url: 飞书Webhook URL
            title: 标题
            content: 内容

        Returns:
            是否推送成功
        """
        try:
            message = {
                "msg_type": "text",
                "content": {
                    "text": f"### {title}\n\n{content}"
                }
            }
            response = requests.post(webhook_url, json=message, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"飞书推送失败: {e}")
            return False

    @staticmethod
    def send_telegram(bot_token: str, chat_id: str, title: str, content: str) -> bool:
        """
        Telegram推送

        Args:
            bot_token: Telegram Bot Token
            chat_id: Chat ID
            title: 标题
            content: 内容

        Returns:
            是否推送成功
        """
        try:
            text = f"<b>{title}</b>\n\n{content}"
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Telegram推送失败: {e}")
            return False

    @staticmethod
    def send_email(
        sender: str,
        password: str,
        receivers: List[str],
        subject: str,
        content: str,
        smtp_server: str = "smtp.qq.com",
        smtp_port: int = 587,
    ) -> bool:
        """
        邮件推送

        Args:
            sender: 发件人邮箱
            password: 邮箱授权码
            receivers: 收件人列表
            subject: 主题
            content: 内容
            smtp_server: SMTP服务器
            smtp_port: SMTP端口

        Returns:
            是否推送成功
        """
        try:
            msg = MIMEMultipart()
            msg["From"] = sender
            msg["To"] = ", ".join(receivers)
            msg["Subject"] = subject
            msg.attach(MIMEText(content, "plain", "utf-8"))

            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, receivers, msg.as_string())
            server.quit()
            return True
        except Exception as e:
            logger.error(f"邮件推送失败: {e}")
            return False


def send_notification(
    title: str,
    content: str,
   渠道: str = "all",
) -> Dict[str, bool]:
    """
    发送通知

    Args:
        title: 标题
        content: 内容
        渠道: 推送渠道

    Returns:
        各渠道推送结果
    """
    results = {}

    # 企业微信
    if 渠道 in ["all", "wechat"]:
        webhook = __import__("os").environ.get("WECHAT_WEBHOOK_URL")
        if webhook:
            results["wechat"] = PushSender.send_wechat_webhook(webhook, title, content)

    # 飞书
    if 渠道 in ["all", "feishu"]:
        webhook = __import__("os").environ.get("FEISHU_WEBHOOK_URL")
        if webhook:
            results["feishu"] = PushSender.send_feishu_webhook(webhook, title, content)

    # Telegram
    if 渠道 in ["all", "telegram"]:
        token = __import__("os").environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = __import__("os").environ.get("TELEGRAM_CHAT_ID")
        if token and chat_id:
            results["telegram"] = PushSender.send_telegram(token, chat_id, title, content)

    # 邮件
    if 渠道 in ["all", "email"]:
        sender = __import__("os").environ.get("EMAIL_SENDER")
        password = __import__("os").environ.get("EMAIL_PASSWORD")
        receivers_str = __import__("os").environ.get("EMAIL_RECEIVERS", "")
        if sender and password and receivers_str:
            receivers = receivers_str.split(",")
            results["email"] = PushSender.send_email(
                sender, password, receivers, title, content
            )

    return results


def send_analysis_notification(
    ticker: str,
    action: str,
    score: int,
    conclusion: str,
    price: float,
) -> Dict[str, bool]:
    """
    发送股票分析通知

    Args:
        ticker: 股票代码
        action: 交易动作
        score: 评分
        conclusion: 结论
        price: 最新价格

    Returns:
        各渠道推送结果
    """
    title = f"📊 {ticker} {action}提醒 (评分: {score})"
    content = f"""
**最新价格**: ¥{price:.2f}

**分析结论**: {conclusion}

**综合评分**: {score}/100

**操作建议**: {action}

---
*本通知由Quant-AI Dashboard系统自动发送*
"""
    return send_notification(title, content)