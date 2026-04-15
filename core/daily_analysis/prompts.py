from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from core.llm_client import Message

from .config import get_bias_threshold


def load_soul_content() -> Optional[str]:
    """按顺序查找身份文档：SOUL_FILE -> 项目根 soul.md/identity.md -> ~/.quant/soul.md"""
    soul_file = os.getenv("SOUL_FILE")
    if soul_file:
        path = Path(soul_file)
        if path.is_absolute() and path.is_file():
            try:
                return path.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        else:
            path = Path.cwd() / soul_file
            if path.is_file():
                try:
                    return path.read_text(encoding="utf-8").strip()
                except Exception:
                    pass

    for name in ("soul.md", "identity.md"):
        path = Path.cwd() / name
        if path.is_file():
            try:
                return path.read_text(encoding="utf-8").strip()
            except Exception:
                pass

    user_soul = Path.home() / ".quant" / "soul.md"
    if user_soul.is_file():
        try:
            return user_soul.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return None


def build_messages(ctx: Dict) -> List[Message]:
    """根据分析上下文构造对 LLM 的对话消息。"""
    bias_threshold = get_bias_threshold()
    structured_context = json.dumps(ctx.get("analysis_brief") or {}, ensure_ascii=False, indent=2)

    system_prompt = (
        "你是一名专业的 A 股/基金交易分析助手。你的职责是基于给定数据，"
        "给出简洁、可追溯、可执行的交易结论，而不是泛泛而谈。\n\n"
        "【工作方式】\n"
        "1. 先明确数据范围与口径，再做结论。必须优先围绕以下维度组织判断：趋势强弱、估值与活跃度、资金关注、市场背景、风险与限制。\n"
        "2. 只能使用上下文里已经提供的数据，不得臆造财报、资金流、行业景气度或政策信息。\n"
        "3. 如果某类关键数据缺失，必须在 limitations 或 risks 中点明，不得装作数据完备。\n"
        f"4. 当价格相对 MA20 的乖离率超过 {bias_threshold:.1f}% 时，必须明确提示追高风险。\n"
        "5. 点位必须和当前价格、波动、区间位置一致；如果缺乏足够依据，就不要强行给出激进买点。\n"
        "6. 结论必须能从数据里追溯出来，至少引用 2 个以上具体维度，不要只写情绪化判断。\n\n"
        "【输出要求】\n"
        "严格输出一个 JSON 对象，不要输出 Markdown，不要解释，不要包代码块。字段包括：\n"
        "conclusion: string  一句话核心结论\n"
        'action: string      "买入" | "卖出" | "观望"\n'
        "score: number       综合评分，范围 0-100\n"
        "buy_price: number|null\n"
        "stop_loss: number|null\n"
        "target_price: number|null\n"
        'checklist: [{ item: string, status: "满足"|"注意"|"不满足" }]\n'
        "highlights: string[]\n"
        "risks: string[]\n"
        "thesis: string[]            3-5 条关键论据，优先按趋势/估值/资金/市场背景组织\n"
        "data_scope: string          用一句话说明这次判断的数据范围与口径\n"
        "limitations: string[]       直接列出数据缺失或结论边界\n"
        "valuation_view: string      对估值与活跃度的简短判断，没有数据就明确写缺失\n"
        "liquidity_view: string      对资金流、换手、量比或市场关注度的简短判断，没有数据就明确写缺失\n\n"
        "如果信息不足以支持明确买入或卖出，默认给出“观望”。"
    )

    try:
        from core.skills import build_skills_prompt_section

        skills_section = build_skills_prompt_section()
        if skills_section:
            system_prompt = system_prompt.rstrip() + "\n\n" + skills_section + "\n"
    except Exception:
        pass

    soul = load_soul_content()
    if soul:
        system_prompt = system_prompt.rstrip() + "\n\n## 身份与原则\n\n" + soul + "\n"

    user_prompt = (
        "请基于下面的结构化上下文和文本上下文，输出交易判断 JSON。\n\n"
        "【结构化上下文】\n"
        f"{structured_context}\n\n"
        "【文本上下文】\n"
        f"{ctx.get('text_context', '')}\n"
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
