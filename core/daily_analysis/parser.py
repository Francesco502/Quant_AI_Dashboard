from __future__ import annotations

import ast
import json
import logging
import re
from typing import Any, Dict, List


logger = logging.getLogger(__name__)

_VALID_ACTIONS = {"买入", "卖出", "观望"}
_VALID_CHECK_STATUS = {"满足", "注意", "不满足"}
_ACTION_ALIASES = {
    "买入": "买入",
    "增持": "买入",
    "加仓": "买入",
    "看多": "买入",
    "buy": "买入",
    "long": "买入",
    "卖出": "卖出",
    "减持": "卖出",
    "清仓": "卖出",
    "看空": "卖出",
    "sell": "卖出",
    "short": "卖出",
    "观望": "观望",
    "持有": "观望",
    "继续持有": "观望",
    "等待": "观望",
    "wait": "观望",
    "watch": "观望",
    "hold": "观望",
}
_CHECK_STATUS_ALIASES = {
    "满足": "满足",
    "是": "满足",
    "yes": "满足",
    "true": "满足",
    "通过": "满足",
    "注意": "注意",
    "中性": "注意",
    "一般": "注意",
    "warn": "注意",
    "warning": "注意",
    "不满足": "不满足",
    "否": "不满足",
    "no": "不满足",
    "false": "不满足",
    "未通过": "不满足",
}


def _extract_json(text: str) -> str:
    """从混杂文本中尽量提取 JSON 对象片段。"""
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", stripped, count=1)
        stripped = re.sub(r"\s*```$", "", stripped, count=1)
    return stripped.strip()


def _normalize_json_like_text(text: str) -> str:
    normalized = (
        str(text or "")
        .strip()
        .replace("\ufeff", "")
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
    )
    normalized = "".join(ch for ch in normalized if ch in "\n\r\t" or ord(ch) >= 32)
    normalized = _strip_code_fences(normalized)
    if normalized.lower().startswith("json"):
        normalized = normalized[4:].lstrip(" \n\r\t:")
    normalized = re.sub(r'(?<=[\'"\]\}0-9A-Za-z])：(?=\s*["\'{\[\-0-9tfn])', ":", normalized)
    normalized = re.sub(r'(?<=[\'"\]\}0-9A-Za-z])，(?=\s*["\'{\[\-0-9tfn])', ",", normalized)
    normalized = normalized.rstrip(";")
    normalized = re.sub(r",\s*([}\]])", r"\1", normalized)
    return normalized.strip()


def _normalize_action(value: Any) -> str:
    raw = str(value or "").strip()
    if raw in _VALID_ACTIONS:
        return raw
    lowered = raw.lower()
    if lowered in _ACTION_ALIASES:
        return _ACTION_ALIASES[lowered]
    return "观望"


def _normalize_check_status(value: Any) -> str:
    raw = str(value or "").strip()
    if raw in _VALID_CHECK_STATUS:
        return raw
    lowered = raw.lower()
    if lowered in _CHECK_STATUS_ALIASES:
        return _CHECK_STATUS_ALIASES[lowered]
    return "注意"


def _normalize_text_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_checklist(value: Any) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        return []

    items: List[Dict[str, str]] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        item = str(raw.get("item") or "").strip()
        if not item:
            continue
        items.append({"item": item, "status": _normalize_check_status(raw.get("status"))})
    return items


def _normalize_score(value: Any) -> int:
    try:
        score = int(round(float(value)))
    except Exception:
        return 50
    return max(0, min(100, score))


def _normalize_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _load_structured_payload(text: str) -> Dict[str, Any] | None:
    raw = str(text or "").strip()
    if not raw:
        return None

    candidates: List[str] = []
    seen = set()
    for candidate in (
        raw,
        _normalize_json_like_text(raw),
        _extract_json(raw),
        _extract_json(_normalize_json_like_text(raw)),
    ):
        normalized = _normalize_json_like_text(candidate)
        if normalized and normalized not in seen:
            seen.add(normalized)
            candidates.append(normalized)

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        try:
            parsed = ast.literal_eval(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    return None


def _extract_inline_value(text: str, keys: List[str]) -> str:
    for key in keys:
        patterns = [
            rf'"{key}"\s*:\s*"([^"]+)"',
            rf"'{key}'\s*:\s*'([^']+)'",
            rf"{key}\s*[:：]\s*([^\n,，]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if value:
                    return value
    return ""


def _heuristic_fallback_decision(raw_text: str, *, meta: Dict[str, Any]) -> Dict[str, Any] | None:
    text = _normalize_json_like_text(raw_text)
    if not text:
        return None

    conclusion = _extract_inline_value(text, ["conclusion", "结论"])
    if not conclusion:
        for line in text.splitlines():
            cleaned = line.strip().lstrip("-*0123456789. ")
            if not cleaned:
                continue
            if any(token in cleaned for token in ("{", "}", "[", "]", '"', "'")):
                continue
            conclusion = cleaned
            break

    action_text = _extract_inline_value(text, ["action", "建议", "操作"])
    if not action_text:
        action_match = re.search(r"(买入|卖出|观望|增持|减持|持有|buy|sell|hold|watch|wait)", text, flags=re.IGNORECASE)
        action_text = action_match.group(1) if action_match else ""

    score_text = _extract_inline_value(text, ["score", "评分"])
    score = _normalize_score(score_text) if score_text else 50

    if not conclusion and not action_text and not score_text:
        return None

    risks = _normalize_text_list(meta.get("limitations"))
    risks.insert(0, "模型输出格式不规范，已按文本兜底解析")

    return {
        "conclusion": conclusion or "模型已返回内容，但格式不规范；建议先观望并复核原始输出。",
        "action": _normalize_action(action_text),
        "score": score,
        "buy_price": _normalize_float(_extract_inline_value(text, ["buy_price", "buyPrice", "参考买点", "买点"])),
        "stop_loss": _normalize_float(_extract_inline_value(text, ["stop_loss", "stopLoss", "止损价", "止损"])),
        "target_price": _normalize_float(_extract_inline_value(text, ["target_price", "targetPrice", "目标价"])),
        "checklist": [],
        "highlights": [],
        "risks": risks,
        "thesis": [],
        "data_scope": "",
        "limitations": _normalize_text_list(meta.get("limitations")),
        "valuation_view": "",
        "liquidity_view": "",
        "raw_text": raw_text,
    }


def parse_decision(raw_text: str, *, meta: Dict[str, Any]) -> Dict[str, Any]:
    """解析 LLM 返回文本为统一决策结构。"""
    data = _load_structured_payload(raw_text)
    if data is None:
        fallback = _heuristic_fallback_decision(raw_text, meta=meta)
        if fallback is not None:
            logger.warning("LLM 决策 JSON 解析失败，已使用文本兜底解析")
            return fallback

        logger.warning("解析 LLM 决策 JSON 失败，将使用占位结构。原始输出预览: %s", raw_text[:500])
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
            "thesis": [],
            "data_scope": "",
            "limitations": _normalize_text_list(meta.get("limitations")),
            "valuation_view": "",
            "liquidity_view": "",
            "raw_text": raw_text,
        }

    decision = {
        "conclusion": str(data.get("conclusion") or "").strip(),
        "action": _normalize_action(data.get("action")),
        "score": _normalize_score(data.get("score")),
        "buy_price": _normalize_float(data.get("buy_price")),
        "stop_loss": _normalize_float(data.get("stop_loss")),
        "target_price": _normalize_float(data.get("target_price")),
        "checklist": _normalize_checklist(data.get("checklist")),
        "highlights": _normalize_text_list(data.get("highlights")),
        "risks": _normalize_text_list(data.get("risks")),
        "thesis": _normalize_text_list(data.get("thesis")),
        "data_scope": str(data.get("data_scope") or "").strip(),
        "limitations": _normalize_text_list(data.get("limitations") or meta.get("limitations")),
        "valuation_view": str(data.get("valuation_view") or "").strip(),
        "liquidity_view": str(data.get("liquidity_view") or "").strip(),
        "raw_text": raw_text,
    }

    return decision
