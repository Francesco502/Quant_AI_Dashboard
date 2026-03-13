from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict


logger = logging.getLogger(__name__)


def _extract_json(text: str) -> str:
    """从混杂文本中尽量提取 JSON 对象片段"""
    # 简单从第一个 { 到最后一个 } 截取
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def parse_decision(raw_text: str, *, meta: Dict[str, Any]) -> Dict[str, Any]:
    """解析 LLM 返回文本为统一决策结构

    若解析失败，将构造一个尽量合理的占位结构，避免接口 500。
    """
    text = raw_text.strip()
    data: Dict[str, Any]

    try:
        # 优先尝试直接解析
        data = json.loads(text)
    except Exception:
        try:
            # 再尝试从文本中抽取 JSON 片段
            json_part = _extract_json(text)
            data = json.loads(json_part)
        except Exception as e:
            logger.warning("解析 LLM 决策 JSON 失败，将使用占位结构: %s", e)
            last_close = meta.get("last_close")
            return {
                "conclusion": "（占位结果）无法解析模型输出，请检查 LLM 配置或重试。",
                "action": "观望",
                "score": 50,
                "buy_price": None,
                "stop_loss": None,
                "target_price": None,
                "checklist": [],
                "highlights": [],
                "risks": ["LLM 输出不可解析"],
                "raw_text": raw_text,
            }

    # 归一化字段与默认值
    def _get(key: str, default: Any) -> Any:
        return data.get(key, default)

    decision = {
        "conclusion": _get("conclusion", ""),
        "action": _get("action", "观望"),
        "score": _get("score", 50),
        "buy_price": _get("buy_price", None),
        "stop_loss": _get("stop_loss", None),
        "target_price": _get("target_price", None),
        "checklist": _get("checklist", []),
        "highlights": _get("highlights", []),
        "risks": _get("risks", []),
        "raw_text": raw_text,
    }

    return decision

