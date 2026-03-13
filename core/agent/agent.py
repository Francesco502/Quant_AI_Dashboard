"""轻量 Agent 核心实现（Dexter 风格精简版）"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import json
import logging
from pathlib import Path

from core.llm_client import chat_completion
from core import scratchpad
from .tools import BaseTool, ToolResult
from .prompts import build_system_prompt, build_iteration_prompt, build_final_answer_prompt


logger = logging.getLogger(__name__)


@dataclass
class AgentState:
    query: str
    model: Optional[str]
    tools: Dict[str, BaseTool]
    scratchpad_path: Optional[Path]
    iteration: int = 0
    max_iterations: int = 3
    tool_results: List[ToolResult] = field(default_factory=list)
    system_prompt: str = ""


def _extract_json(text: str) -> str:
    """从混杂文本中尽量提取 JSON 片段。"""
    s = text.strip()
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        return s[start : end + 1]
    return s


def _parse_plan(text: str) -> Tuple[str, List[Dict[str, Any]], Optional[str]]:
    """解析 LLM 的规划 JSON，返回 (thoughts, tool_calls, final_answer)。"""
    try:
        json_text = _extract_json(text)
        obj = json.loads(json_text)
    except Exception as e:  # noqa: BLE001
        logger.warning("解析 Agent 规划 JSON 失败，将视为直接回答: %s", e)
        return "", [], text.strip()

    thoughts = str(obj.get("thoughts") or "")
    final_answer = obj.get("final_answer")
    if isinstance(final_answer, str):
        final_answer_str: Optional[str] = final_answer or None
    else:
        final_answer_str = None
    calls = obj.get("tool_calls") or []
    if not isinstance(calls, list):
        calls = []
    tool_calls: List[Dict[str, Any]] = []
    for item in calls:
        if not isinstance(item, dict):
            continue
        name = str(item.get("tool") or "").strip()
        args = item.get("args") or {}
        if not name:
            continue
        if not isinstance(args, dict):
            try:
                args = dict(args)  # type: ignore[arg-type]
            except Exception:
                args = {}
        tool_calls.append({"tool": name, "args": args})
    return thoughts, tool_calls, final_answer_str


def run_agent(state: AgentState) -> Dict[str, Any]:
    """执行轻量 Agent 循环，返回统一结果结构。"""
    # 准备 system prompt
    state.system_prompt = build_system_prompt(state.tools)

    final_answer: Optional[str] = None

    while state.iteration < state.max_iterations:
        state.iteration += 1

        user_prompt = build_iteration_prompt(
            query=state.query,
            tool_results=state.tool_results,
            iteration=state.iteration,
            max_iterations=state.max_iterations,
        )

        messages = [
            {"role": "system", "content": state.system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # 记录 LLM 调用
        raw_reply = chat_completion(messages, model=state.model)
        if state.scratchpad_path is not None:
            scratchpad.append_llm_call(
                state.scratchpad_path,
                model=state.model or "",
                prompt_token_estimate=min(8192, len(user_prompt) // 2),
                response_preview=raw_reply[:500] if raw_reply else "",
            )

        thoughts, tool_calls, maybe_final = _parse_plan(raw_reply)

        if state.scratchpad_path is not None and thoughts:
            scratchpad.append_thinking(state.scratchpad_path, thoughts)

        # 若 LLM 给出了 final_answer 且未请求调用工具，则可以直接结束
        if maybe_final and not tool_calls:
            final_answer = maybe_final
            break

        if not tool_calls:
            # 没有工具计划也没有 final_answer，认为需要进入最后总结阶段
            break

        # 执行工具调用
        for call in tool_calls:
            tool_name = call["tool"]
            args = call["args"]
            tool = state.tools.get(tool_name)
            if not tool:
                logger.warning("Agent 收到未知工具名称: %s", tool_name)
                continue
            try:
                result = tool.run(**args)
            except Exception as e:  # noqa: BLE001
                logger.warning("Agent 工具 %s 调用失败: %s", tool_name, e)
                result = ToolResult(
                    name=tool_name,
                    args=args,
                    data={"error": str(e), "tool": tool_name},
                )
            state.tool_results.append(result)

            if state.scratchpad_path is not None:
                preview = json.dumps(result.data, ensure_ascii=False)[:400]
                scratchpad.append_tool_result(
                    state.scratchpad_path,
                    tool_name=tool_name,
                    args=result.args,
                    data_preview=preview,
                )

    # 若尚未获得 final_answer，则用最后一轮总结 prompt 生成
    if final_answer is None:
        final_prompt = build_final_answer_prompt(state.query, state.tool_results)
        messages = [
            {"role": "system", "content": state.system_prompt},
            {"role": "user", "content": final_prompt},
        ]
        final_answer = chat_completion(messages, model=state.model)
        if state.scratchpad_path is not None:
            scratchpad.append_llm_call(
                state.scratchpad_path,
                model=state.model or "",
                prompt_token_estimate=min(8192, len(final_prompt) // 2),
                response_preview=final_answer[:500] if final_answer else "",
            )

    return {
        "answer": final_answer or "",
        "iterations": state.iteration,
        "tools_used": [tr.name for tr in state.tool_results],
        "tool_results": [
            {"name": tr.name, "args": tr.args, "data": tr.data} for tr in state.tool_results
        ],
        "scratchpad_path": str(state.scratchpad_path) if state.scratchpad_path else None,
    }

