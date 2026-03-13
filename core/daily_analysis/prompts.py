from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

from core.llm_client import Message
from .config import get_bias_threshold


def load_soul_content() -> Optional[str]:
    """按顺序查找身份文档：SOUL_FILE -> 项目根 soul.md/identity.md -> ~/.quant/soul.md"""
    # 1. 环境变量指定
    soul_file = os.getenv("SOUL_FILE")
    if soul_file:
        p = Path(soul_file)
        if p.is_absolute() and p.is_file():
            try:
                return p.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        else:
            p = Path.cwd() / soul_file
            if p.is_file():
                try:
                    return p.read_text(encoding="utf-8").strip()
                except Exception:
                    pass
    # 2. 项目根
    for name in ("soul.md", "identity.md"):
        p = Path.cwd() / name
        if p.is_file():
            try:
                return p.read_text(encoding="utf-8").strip()
            except Exception:
                pass
    # 3. 用户目录
    user_soul = Path.home() / ".quant" / "soul.md"
    if user_soul.is_file():
        try:
            return user_soul.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return None


def build_messages(ctx: Dict) -> List[Message]:
    """根据分析上下文构造对 LLM 的对话消息"""
    bias_threshold = get_bias_threshold()

    system_prompt = (
        "你是一名专业的股票与量化交易分析师，需要基于给定的技术面与行情信息，"
        "对单只标的给出简洁、可执行的交易决策。"
        "\n\n"
        "【内置交易纪律】\n"
        f"1. 严禁追高：当价格相对 MA20 的乖离率超过 {bias_threshold:.1f}% 时，必须提示存在追高风险；"
        "   对于极强趋势股，可以适度宽容，但仍需明确风险。\n"
        "2. 趋势交易：重点关注 MA5 > MA10 > MA20 的多头排列，若不满足则偏向谨慎或观望。\n"
        "3. 精确点位：给出【买入价】【止损价】【目标价】，三者需与当前价格及波动特征一致，不要脱离现实价格区间。\n"
        "4. 操作检查清单：将关键判断拆分为若干条，每条标记为“满足/注意/不满足”。\n"
        "5. 若上下文中有筹码分布或舆情摘要，请在判断中参考。\n"
        "\n"
        "【输出要求】\n"
        "严格输出一个 JSON 对象（不要包含额外说明或 Markdown），字段包括：\n"
        "conclusion: string  一句话核心结论（简短中文）\n"
        "action: string      建议操作：\"买入\" | \"卖出\" | \"观望\"\n"
        "score: number       综合评分（0-100）\n"
        "buy_price: number|null      建议买入价\n"
        "stop_loss: number|null      建议止损价\n"
        "target_price: number|null   建议目标价\n"
        "checklist: [{ item: string, status: \"满足\"|\"注意\"|\"不满足\" }]\n"
        "highlights: string[]  主要利好或优势\n"
        "risks: string[]       主要风险点\n"
        "\n"
        "若信息不足以给出明确买入/卖出建议，应倾向“观望”，并在 risks 中说明原因。"
    )

    # Skills 段落（Dexter 借鉴）
    try:
        from core.skills import build_skills_prompt_section
        skills_section = build_skills_prompt_section()
        if skills_section:
            system_prompt = system_prompt.rstrip() + "\n\n" + skills_section + "\n"
    except Exception:
        pass

    # SOUL 身份与原则（Dexter 借鉴）
    soul = load_soul_content()
    if soul:
        system_prompt = system_prompt.rstrip() + "\n\n## 身份与原则\n\n" + soul + "\n"

    user_prompt = (
        "下面是某个标的的基础行情与技术面信息，请结合内置交易纪律，"
        "生成上述要求格式的 JSON 决策结果。\n\n"
        "【标的信息】\n"
        f"{ctx.get('text_context', '')}\n"
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

