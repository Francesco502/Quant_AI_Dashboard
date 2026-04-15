from core.daily_analysis.parser import parse_decision


def test_parse_decision_keeps_extended_fields_and_normalizes_values():
    raw = """
    {
      "conclusion": "趋势偏强但短线不宜追高",
      "action": "买入",
      "score": 81.6,
      "buy_price": "101.25",
      "stop_loss": 96,
      "target_price": 110.5,
      "checklist": [
        {"item": "MA5>MA10>MA20", "status": "满足"},
        {"item": "量价配合", "status": "未知"}
      ],
      "highlights": ["20日涨幅领先", "北向资金偏正"],
      "risks": ["乖离率偏高"],
      "thesis": ["趋势维持多头", "估值未明显失真"],
      "data_scope": "基于近一年收盘价和最近一期 Tushare 每日指标",
      "limitations": ["缺少财报盈利预告"],
      "valuation_view": "PE(TTM) 处于中性区间",
      "liquidity_view": "最近主力净流入为正"
    }
    """

    result = parse_decision(raw, meta={"limitations": ["meta fallback"]})

    assert result["action"] == "买入"
    assert result["score"] == 82
    assert result["buy_price"] == 101.25
    assert result["checklist"][1]["status"] == "注意"
    assert result["thesis"] == ["趋势维持多头", "估值未明显失真"]
    assert result["limitations"] == ["缺少财报盈利预告"]
    assert result["valuation_view"] == "PE(TTM) 处于中性区间"


def test_parse_decision_uses_meta_limitations_on_fallback():
    result = parse_decision("not-json", meta={"limitations": ["缺少 Tushare 每日指标"]})

    assert result["action"] == "观望"
    assert result["limitations"] == ["缺少 Tushare 每日指标"]


def test_parse_decision_recovers_from_markdown_code_fence_and_trailing_comma():
    raw = """
    ```json
    {
      "conclusion": "趋势转强，但不宜重仓追涨",
      "action": "买入",
      "score": 73,
      "buy_price": 10.25,
      "stop_loss": 9.8,
      "target_price": 11.2,
      "highlights": ["量价配合改善"],
      "risks": ["短线波动仍在"],
    }
    ```
    """

    result = parse_decision(raw, meta={"limitations": []})

    assert result["conclusion"] == "趋势转强，但不宜重仓追涨"
    assert result["action"] == "买入"
    assert result["score"] == 73
    assert result["buy_price"] == 10.25
    assert result["target_price"] == 11.2


def test_parse_decision_recovers_from_single_quoted_payload():
    raw = """
    {
      'conclusion': '估值一般，继续观察',
      'action': 'hold',
      'score': 61,
      'buy_price': None,
      'stop_loss': None,
      'target_price': None,
      'checklist': [{'item': '回撤受控', 'status': 'yes'}],
      'risks': ['成交活跃度偏弱']
    }
    """

    result = parse_decision(raw, meta={"limitations": ["缺少资金流数据"]})

    assert result["action"] == "观望"
    assert result["score"] == 61
    assert result["checklist"] == [{"item": "回撤受控", "status": "满足"}]
    assert result["risks"] == ["成交活跃度偏弱"]
