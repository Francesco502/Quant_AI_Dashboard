"""
WebSocket 管理器

管理 WebSocket 连接和消息推送
"""

from fastapi import WebSocket
from typing import List, Dict, Any
import json
import logging

logger = logging.getLogger(__name__)


class WebSocketManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """接受新的 WebSocket 连接"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket 连接已建立，当前连接数: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """断开 WebSocket 连接"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket 连接已断开，当前连接数: {len(self.active_connections)}")

    async def send_personal_message(self, message: Any, websocket: WebSocket):
        """向特定客户端发送消息"""
        try:
            if isinstance(message, dict):
                message = json.dumps(message, ensure_ascii=False, default=str)
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"发送 WebSocket 消息失败: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: Any):
        """向所有连接的客户端广播消息"""
        disconnected = []
        for connection in self.active_connections:
            try:
                if isinstance(message, dict):
                    message_str = json.dumps(message, ensure_ascii=False, default=str)
                else:
                    message_str = message
                await connection.send_text(message_str)
            except Exception as e:
                logger.error(f"广播消息失败: {e}")
                disconnected.append(connection)

        # 移除断开的连接
        for conn in disconnected:
            self.disconnect(conn)

