"""
Agent 评估运行器：对比 Agent 输出与现有 daily_analysis 表现

用法：
  python -m evals.run_evals_agent
  python evals/run_evals_agent.py
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATASET_PATH = Path(__file__).parent / "dataset" / "llm_analysis_evals.csv"
REPORTS_DIR = Path(__file__).parent / "reports"

JUDGE_SYSTEM = """你是一个评估助手。根据「题目」「参考要点」和「模型输出」，给出 0～1 的分数和简短理由。
输出严格为一行 JSON，不要换行或多余文字：{"score": 0.0~1.0, "reason": "一句话理由"}"""


def load_dataset() -> List[Dict[str, str]]:
    if not DATASET_PATH.is_file():
        return []
    rows: List[Dict[str, str]] = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("question") and row.get("ticker"):
                rows.append(row)
    return rows


def judge_output(question: str, reference_points: str, model_output: str) -> Dict[str, Any]:
    from core.llm_client import chat_completion

    user_content = (
        f"【题目】{question}\n"
        f"【参考要点】{reference_points}\n"
        f"【模型输出】\n{model_output}\n\n"
        "请输出一行 JSON：{\"score\": 0.0~1.0, \"reason\": \"...\"}"
    )
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": user_content},
    ]
    text = chat_completion(messages).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        obj = json.loads(text)
        return {
            "score": float(obj.get("score", 0.0)),
            "reason": str(obj.get("reason", "")),
        }
    except Exception as e:  # noqa: BLE001
        return {"score": 0.0, "reason": f"judge parse error: {e}"}


def run_evals_agent() -> Dict[str, Any]:
    """对比 Agent 与 daily_analysis 的表现。"""
    from core.daily_analysis import run_daily_analysis
    from core.agent import run_agent

    dataset = load_dataset()
    if not dataset:
        return {"error": "dataset empty or missing", "results": [], "avg_score_daily": 0.0, "avg_score_agent": 0.0}

    results: List[Dict[str, Any]] = []
    daily_scores: List[float] = []
    agent_scores: List[float] = []

    for row in dataset:
        question = row.get("question", "")
        ticker = row.get("ticker", "")
        market = row.get("market", "cn")
        reference_points = row.get("reference_points", "")
        question_type = row.get("question_type", "")

        # 1) baseline: daily_analysis
        try:
            out = run_daily_analysis(tickers=[ticker], market=market, include_market_review=False)
            res_list = out.get("results") or []
            decision = {}
            if res_list:
                decision = res_list[0].get("decision") or {}
            daily_output_str = json.dumps(decision, ensure_ascii=False) if decision else "{}"
        except Exception as e:  # noqa: BLE001
            daily_output_str = f"Error: {e}"

        daily_judge = judge_output(question, reference_points, daily_output_str)
        daily_score = float(daily_judge.get("score", 0.0))
        daily_scores.append(daily_score)

        # 2) agent
        agent_query = f"{question}（标的: {ticker}, 市场: {market}）"
        try:
            agent_result = run_agent(query=agent_query, model=None)
            agent_output_str = str(agent_result.get("answer") or "")
        except Exception as e:  # noqa: BLE001
            agent_output_str = f"Error: {e}"

        agent_judge = judge_output(question, reference_points, agent_output_str)
        agent_score = float(agent_judge.get("score", 0.0))
        agent_scores.append(agent_score)

        results.append(
            {
                "question": question,
                "ticker": ticker,
                "market": market,
                "question_type": question_type,
                "daily": {
                    "score": daily_score,
                    "reason": daily_judge.get("reason", ""),
                    "output_preview": daily_output_str[:500],
                },
                "agent": {
                    "score": agent_score,
                    "reason": agent_judge.get("reason", ""),
                    "output_preview": agent_output_str[:500],
                },
            }
        )

    avg_daily = sum(daily_scores) / len(daily_scores) if daily_scores else 0.0
    avg_agent = sum(agent_scores) / len(agent_scores) if agent_scores else 0.0

    report = {
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "avg_score_daily": round(avg_daily, 4),
        "avg_score_agent": round(avg_agent, 4),
        "results": results,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"evals_agent_report_{ts}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    report["report_path"] = str(report_path)

    return report


def main() -> None:
    report = run_evals_agent()
    if report.get("error"):
        print(report["error"])
        sys.exit(1)
    print(f"Total: {report['total']}, Avg daily: {report['avg_score_daily']:.4f}, Avg agent: {report['avg_score_agent']:.4f}")
    print(f"Report: {report.get('report_path', '')}")


if __name__ == "__main__":
    main()

