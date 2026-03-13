"""Agent 专用 Prompt 模块（Dexter 风格精简版）"""

from __future__ import annotations

from typing import Dict, List
import json

from core.agent.tools import BaseTool, ToolResult
from core.skills import build_skills_prompt_section
from core.daily_analysis.prompts import load_soul_content


def build_system_prompt(tools: Dict[str, BaseTool]) -> str:
    """构建 Agent 的 system prompt，包含工具列表、Skills 与 SOUL。"""
    lines: List[str] = []
    lines.append("你是一名面向股票与宏观市场的深度研究型 AI 助手。")
    lines.append("你可以通过一组“工具”来获取价格历史、大盘复盘、新闻舆情以及现有的技术+舆情决策结果。")
    lines.append("")
    lines.append("【可用工具】")
    for name, tool in tools.items():
        lines.append(f"- {name}: {tool.description}")
    lines.append("")
    lines.append("使用工具的原则：")
    lines.append("1. 只有在现有信息不足以回答问题时才调用工具；")
    lines.append("2. 优先重用已经得到的工具结果，避免重复请求；")
    lines.append("3. 如果某个工具多次调用仍然失败，应在最终回答中说明数据缺失或不可靠。")

    # Skills 段落
    skills_section = build_skills_prompt_section()
    if skills_section:
        lines.append("")
        lines.append(skills_section)

    # SOUL 身份与原则
    soul = load_soul_content()
    if soul:
        lines.append("")
        lines.append("## 身份与原则")
        lines.append("")
        lines.append(soul)

    lines.append("")
    lines.append("在每一轮规划中，你需要先简要说明自己的思考，再给出下一步的工具调用计划或直接给出结论。")
    lines.append("当你认为已有信息足够时，应停止调用工具，转而直接回答用户问题。")

    return "\n".join(lines)


def _summarize_tool_results(tool_results: List[ToolResult], max_len: int = 2000) -> str:
    """将已有工具结果压缩为适合放入 prompt 的摘要字符串。"""
    if not tool_results:
        return "目前尚未调用任何工具。"
    parts: List[str] = []
    for idx, tr in enumerate(tool_results[-5:], start=1):
        preview = json.dumps(tr.data, ensure_ascii=False)[:400]
        parts.append(f"[{idx}] 工具 {tr.name} 调用，参数={tr.args}，结果预览={preview}")
    text = "\n".join(parts)
    if len(text) > max_len:
        return text[:max_len] + "...(截断)"
    return text


def build_iteration_prompt(query: str, tool_results: List[ToolResult], iteration: int, max_iterations: int) -> str:
    """构建每一轮规划用的 user prompt。"""
    summary = _summarize_tool_results(tool_results)
    return (
        f"用户原始问题：\n{query}\n\n"
        f"当前迭代轮次：{iteration}/{max_iterations}\n\n"
        "【目前已掌握的信息】\n"
        f"{summary}\n\n"
        "【你的任务】\n"
        "1. 先用中文简要说明你的思考过程（thoughts）。\n"
        "2. 决定下一步是否需要调用工具，或可以直接给出结论。\n\n"
        "输出严格为一个 JSON 对象，不要包含多余文字，格式：\n"
        "{\n"
        '  \"thoughts\": \"...\",\n'
        '  \"tool_calls\": [\n'
        '    {\"tool\": \"price\"|\"market_review\"|\"news\"|\"daily_decision\", \"args\": { ... }}\n'
        "  ],\n"
        '  \"final_answer\": null 或 \"当你认为信息足够时，在这里给出最终中文回答\"\n'
        "}\n"
        "注意：\n"
        "- 当 tool_calls 为空且 final_answer 非空时，表示你认为可以结束并直接回答。\n"
        "- 当需要调用多个工具时，请在 tool_calls 数组中列出多个条目。\n"
    )


def build_final_answer_prompt(query: str, tool_results: List[ToolResult]) -> str:
    """在工具调用结束后，构建最终回答用的 prompt。"""
    summary = _summarize_tool_results(tool_results, max_len=4000)
    return (
        f"用户原始问题：\n{query}\n\n"
        "下面是你在整个研究过程中调用的工具结果摘要：\n"
        f"{summary}\n\n"
        "现在请基于这些数据，用中文给出一个结构化的最终回答，要求：\n"
        "1. 先用 1～2 段话总结核心结论；\n"
        "2. 用要点列表解释你是如何得到这些结论的，引用关键数据点；\n"
        "3. 指出主要不确定性与潜在风险；\n"
        "4. 如果数据明显不足以支持强结论，请在回答中明确说明这一点。\n"
    )

