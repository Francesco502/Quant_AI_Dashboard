"""
Evals 运行器：数据集 + LLM-as-judge（Dexter 借鉴）

用法：
  python -m evals.run_evals
  python evals/run_evals.py
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

# 项目根
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATASET_PATH = Path(__file__).parent / "dataset" / "llm_analysis_evals.csv"
REPORTS_DIR = Path(__file__).parent / "reports"

JUDGE_SYSTEM = """你是一个评估助手。根据「题目」「参考要点」和「模型输出」，给出 0～1 的分数和简短理由。
输出严格为一行 JSON，不要换行或多余文字：{"score": 0.0~1.0, "reason": "一句话理由"}"""


def load_dataset() -> list[dict]:
    """加载 CSV 数据集。"""
    if not DATASET_PATH.is_file():
        return []
    rows = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("question") and row.get("ticker"):
                rows.append(row)
    return rows


def run_evals() -> dict:
    """执行一轮评估，返回报告结构。"""
    from core.daily_analysis import run_daily_analysis
    from core.llm_client import chat_completion

    dataset = load_dataset()
    if not dataset:
        return {"error": "dataset empty or missing", "results": [], "avg_score": 0.0}

    results = []
    for i, row in enumerate(dataset):
        question = row.get("question", "")
        ticker = row.get("ticker", "")
        market = row.get("market", "cn")
        reference_points = row.get("reference_points", "")
        question_type = row.get("question_type", "")

        # 调用每日分析
        try:
            out = run_daily_analysis(tickers=[ticker], market=market, include_market_review=False)
            res_list = out.get("results") or []
            decision = {}
            model_output_str = ""
            if res_list:
                decision = res_list[0].get("decision") or {}
                if isinstance(decision, dict):
                    model_output_str = json.dumps(decision, ensure_ascii=False)
                else:
                    model_output_str = str(decision)
        except Exception as e:
            model_output_str = f"Error: {e}"
            decision = {}

        # LLM-as-judge
        user_content = (
            f"【题目】{question}\n"
            f"【参考要点】{reference_points}\n"
            f"【模型输出】\n{model_output_str}\n\n"
            "请输出一行 JSON：{\"score\": 0.0~1.0, \"reason\": \"...\"}"
        )
        try:
            judge_messages = [
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": user_content},
            ]
            judge_text = chat_completion(judge_messages)
            judge_text = judge_text.strip()
            if judge_text.startswith("```"):
                judge_text = judge_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            judge = json.loads(judge_text)
            score = float(judge.get("score", 0))
            reason = str(judge.get("reason", ""))
        except Exception as e:
            score = 0.0
            reason = str(e)

        results.append({
            "question": question,
            "ticker": ticker,
            "market": market,
            "question_type": question_type,
            "score": score,
            "reason": reason,
            "model_output_preview": (model_output_str or "")[:500],
        })

    avg = sum(r["score"] for r in results) / len(results) if results else 0.0
    report = {
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "avg_score": round(avg, 4),
        "results": results,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"evals_report_{ts}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    report["report_path"] = str(report_path)

    return report


def main():
    report = run_evals()
    if report.get("error"):
        print(report["error"])
        sys.exit(1)
    print(f"Total: {report['total']}, Avg score: {report['avg_score']:.4f}")
    print(f"Report: {report.get('report_path', '')}")
    for r in report.get("results", []):
        print(f"  [{r['score']:.2f}] {r['ticker']} - {r['reason'][:60]}...")


if __name__ == "__main__":
    main()
