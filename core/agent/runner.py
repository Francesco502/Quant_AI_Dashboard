"""Agent Runner 封装：对外提供 run_agent(query, model) 接口"""

from __future__ import annotations

from typing import Any, Dict, Optional
from pathlib import Path

from core import scratchpad
from .tools import get_default_tools
from .agent import AgentState, run_agent as _run_agent_impl


def run_agent(query: str, model: Optional[str] = None, *, max_iterations: int = 2) -> Dict[str, Any]:
    """执行一轮 Agent 研究流程，返回统一结果结构。

    - query: 自然语言问题（如“比较 600519 和 000858 的估值与风险”）；
    - model: 可选，显式指定本次使用的 LLM 模型名；
    - max_iterations: 最多规划+工具调用轮数。
    """
    tools = dict(get_default_tools())

    scratchpad_path: Optional[Path] = None
    if scratchpad.is_scratchpad_enabled():
        # 使用固定前缀，避免与 daily_analysis 的 ticker / market 混淆
        request_id = scratchpad.generate_request_id("AGENT", "research")
        scratchpad_path = scratchpad.create_scratchpad(
            request_id=request_id,
            ticker="AGENT",
            market="research",
            text_context_preview=query[:500],
        )

    state = AgentState(
        query=query,
        model=model,
        tools=tools,
        scratchpad_path=scratchpad_path,
        max_iterations=max_iterations,
    )

    result = _run_agent_impl(state)
    return result

