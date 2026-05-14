from __future__ import annotations

import datetime as dt
import json
import sqlite3

import pytest

from scripts.daily_asset_report import (
    AssetStore,
    DailyAssetEngine,
    DEFAULT_CONFIG,
    DEFAULT_STORE,
    PricePoint,
    ReportTarget,
    apply_config,
    build_markdown_report,
    format_money,
    import_dashboard_db,
    render_output,
    resolve_script_path,
    resolve_asset_type,
)


class StaticPriceProvider:
    def __init__(self, series):
        self.series = series
        self.calls = 0

    def fetch_series(self, ticker, *, asset_name, asset_type, days):
        self.calls += 1
        return list(self.series.get(ticker, []))


def _sample_overview():
    return {
        "summary": {
            "asset_count": 2,
            "total_market_value": 11000.0,
            "total_invested_amount": 10000.0,
            "total_return": 1000.0,
            "total_return_pct": 10.0,
            "day_change": 50.0,
            "week_change": -20.0,
            "month_change": 120.0,
            "year_change": 1000.0,
            "updated_at": "2026-04-23T16:00:00",
        },
        "assets": [
            {
                "ticker": "002611",
                "asset_name": "Gold Fund",
                "current_price": 2.5,
                "last_price_date": "2026-04-23",
                "market_value": 5000.0,
                "day_change": 60.0,
                "day_change_pct": 1.2,
                "total_return": 500.0,
                "total_return_pct": 11.11,
                "pending_dca": {
                    "status": "pending_confirmation",
                    "amount": 100.0,
                    "execution_date": "2026-04-23",
                    "confirmation_date": "2026-04-24",
                    "price_basis_date": "2026-04-23",
                    "estimated_price": 2.0,
                    "estimated_units": 50.0,
                },
            },
            {
                "ticker": "160615",
                "asset_name": "CSI 300 Fund",
                "current_price": 1.5,
                "last_price_date": "2026-04-23",
                "market_value": 6000.0,
                "day_change": -10.0,
                "day_change_pct": -0.2,
                "total_return": 500.0,
                "total_return_pct": 9.09,
            },
        ],
        "warnings": [],
    }


def test_format_money_with_signed_values():
    assert format_money(12.3, signed=True) == "+¥12.30"
    assert format_money(-12.3, signed=True) == "-¥12.30"
    assert format_money(0, signed=True) == "¥0.00"


def test_asset_type_resolution_keeps_linked_fund_as_fund():
    assert resolve_asset_type("160615", asset_name="鹏华沪深300ETF联接(LOF)A", asset_type="fund") == "fund"
    assert resolve_asset_type("159755", asset_name="电池ETF", asset_type="fund") == "etf"
    assert resolve_asset_type("002611", asset_name="博时黄金ETF联接C", asset_type=None) == "fund"
    assert resolve_asset_type("006195", asset_name="国金量化多因子股票A", asset_type=None) == "fund"
    assert resolve_asset_type("006810", asset_name="泰康港股通中证香港银行投资指数C", asset_type=None) == "fund"


def test_default_agent_files_live_under_scripts():
    assert DEFAULT_STORE.parent.name == "scripts"
    assert DEFAULT_CONFIG.parent.name == "scripts"
    assert resolve_script_path("custom.db").parent == DEFAULT_STORE.parent


def test_build_markdown_report_contains_agent_ready_summary():
    report = build_markdown_report(
        ReportTarget(username="admin"),
        _sample_overview(),
        reconcile={"created": 1, "rules_checked": 3, "as_of": "2026-04-23"},
        generated_at=dt.datetime(2026, 4, 23, 18, 30),
        top_limit=1,
    )

    assert "# 个人资产日报 - admin" in report
    assert "累计收益: +¥1,000.00 (+10.00%)" in report
    assert "今日收益: +¥50.00" in report
    assert "定投补算: 新增 1 笔 / 检查 3 条 / 日期 2026-04-23" in report
    assert "Gold Fund (002611)" in report
    assert "CSI 300 Fund (160615)" not in report
    assert "## 待确认定投" in report
    assert "估算份额 50.0000" in report


def test_standalone_engine_reconciles_dca_and_values_assets_from_config(tmp_path):
    config_path = tmp_path / "assets.json"
    config_path.write_text(
        json.dumps(
            {
                "username": "agent",
                "assets": [
                    {
                        "ticker": "002611",
                        "asset_name": "博时黄金ETF联接C",
                        "asset_type": "fund",
                        "units": 0,
                        "avg_cost": 0,
                        "trade_date": "2026-03-18",
                        "dca_rule": {
                            "enabled": True,
                            "frequency": "weekly",
                            "weekday": 3,
                            "amount": 100,
                            "start_date": "2026-03-19",
                            "shift_to_next_trading_day": True,
                        },
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    store = AssetStore(tmp_path / "agent_assets.db")
    try:
        apply_config(store, config_path, replace=True)
        provider = StaticPriceProvider(
            {
                "002611": [
                    PricePoint(dt.date(2026, 3, 19), 2.00, "test"),
                    PricePoint(dt.date(2026, 3, 20), 2.05, "test"),
                ]
            }
        )
        engine = DailyAssetEngine(store, provider)

        thursday = engine.reconcile_due_dca(as_of=dt.date(2026, 3, 19))
        assert thursday["created"] == 0
        pending = engine.get_overview(refresh_prices=False, as_of=dt.date(2026, 3, 19))["assets"][0]["pending_dca"]
        assert pending["confirmation_date"] == "2026-03-20"
        assert pending["estimated_units"] == pytest.approx(50.0)

        friday = engine.reconcile_due_dca(as_of=dt.date(2026, 3, 20))
        assert friday["created"] == 1
        overview = engine.get_overview(refresh_prices=False, as_of=dt.date(2026, 3, 20))
        asset = overview["assets"][0]

        assert asset["units"] == pytest.approx(50.0)
        assert asset["invested_amount"] == pytest.approx(100.0)
        assert asset["current_price"] == pytest.approx(2.05)
        assert asset["total_return"] == pytest.approx(2.5)
        assert asset["day_change"] == pytest.approx(2.5)
        assert asset["pending_dca"] is None
    finally:
        store.close()


def test_skip_price_refresh_uses_cache_only(tmp_path):
    config_path = tmp_path / "assets.json"
    config_path.write_text(
        json.dumps(
            {
                "assets": [
                    {
                        "ticker": "002611",
                        "asset_name": "博时黄金ETF联接C",
                        "asset_type": "fund",
                        "units": 10,
                        "avg_cost": 2.5,
                        "trade_date": "2026-04-23",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    store = AssetStore(tmp_path / "agent_assets.db")
    try:
        apply_config(store, config_path, replace=True)
        provider = StaticPriceProvider({"002611": [PricePoint(dt.date(2026, 4, 24), 3.0, "test")]})
        engine = DailyAssetEngine(store, provider)

        overview = engine.get_overview(refresh_prices=False, as_of=dt.date(2026, 4, 24))

        assert provider.calls == 0
        assert overview["assets"][0]["current_price"] == pytest.approx(2.5)
        assert "无行情数据" in overview["warnings"][0]
    finally:
        store.close()


def test_refresh_when_cache_is_recent_but_too_short():
    series = [
        PricePoint(dt.date(2026, 4, 20), 1.0, "test"),
        PricePoint(dt.date(2026, 4, 27), 1.1, "test"),
    ]

    assert DailyAssetEngine.should_refresh(series, "fund", dt.date(2026, 4, 28), days=400)


def test_as_of_report_excludes_future_prices_and_transactions(tmp_path):
    config_path = tmp_path / "assets.json"
    config_path.write_text(
        json.dumps(
            {
                "assets": [
                    {
                        "ticker": "002611",
                        "asset_name": "博时黄金ETF联接C",
                        "asset_type": "fund",
                        "units": 10,
                        "avg_cost": 2.0,
                        "trade_date": "2026-04-01",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    store = AssetStore(tmp_path / "agent_assets.db")
    try:
        apply_config(store, config_path, replace=True)
        store.save_price_points(
            "002611",
            [
                PricePoint(dt.date(2026, 4, 24), 3.0, "test"),
                PricePoint(dt.date(2026, 4, 27), 4.0, "test"),
            ],
        )
        store.insert_transaction(
            "002611",
            {
                "transaction_type": "BUY",
                "trade_date": "2026-04-26",
                "quantity": 10,
                "price": 5.0,
                "amount": 50.0,
                "source": "test",
            },
            source_id="future-buy",
        )
        engine = DailyAssetEngine(store, StaticPriceProvider({}))

        overview = engine.get_overview(refresh_prices=False, as_of=dt.date(2026, 4, 24))
        asset = overview["assets"][0]

        assert asset["last_price_date"] == "2026-04-24"
        assert asset["current_price"] == pytest.approx(3.0)
        assert asset["units"] == pytest.approx(10.0)
        assert asset["market_value"] == pytest.approx(30.0)
        assert asset["total_return"] == pytest.approx(10.0)
    finally:
        store.close()


def test_dashboard_import_copies_snapshots(tmp_path):
    source_db = tmp_path / "quant.db"
    con = sqlite3.connect(source_db)
    try:
        con.executescript(
            """
            CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT);
            CREATE TABLE user_asset_holdings(
                user_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                asset_name TEXT,
                asset_category TEXT,
                asset_style TEXT,
                asset_type TEXT,
                notes TEXT
            );
            CREATE TABLE user_asset_transactions(
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                amount REAL,
                fee REAL NOT NULL DEFAULT 0,
                source TEXT,
                note TEXT
            );
            CREATE TABLE user_asset_dca_rules(
                user_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                enabled INTEGER,
                frequency TEXT,
                weekday INTEGER,
                monthday INTEGER,
                amount REAL,
                start_date TEXT,
                end_date TEXT,
                shift_to_next_trading_day INTEGER,
                last_run_date TEXT
            );
            CREATE TABLE user_asset_snapshots(
                user_id INTEGER NOT NULL,
                snapshot_date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                current_price REAL NOT NULL,
                units REAL NOT NULL,
                market_value REAL NOT NULL,
                invested_amount REAL NOT NULL,
                total_return REAL NOT NULL,
                total_return_pct REAL NOT NULL,
                created_at TEXT
            );
            """
        )
        con.execute("INSERT INTO users(id, username) VALUES(1, 'admin')")
        con.execute(
            "INSERT INTO user_asset_holdings(user_id, ticker, asset_name, asset_type) VALUES(1, '002611', '博时黄金ETF联接C', 'fund')"
        )
        con.execute(
            """
            INSERT INTO user_asset_transactions(
                id, user_id, ticker, transaction_type, trade_date, quantity, price, amount, fee, source
            )
            VALUES(7, 1, '002611', 'RESET', '2026-04-01', 10, 2, 20, 0, 'manual')
            """
        )
        con.execute(
            """
            INSERT INTO user_asset_snapshots(
                user_id, snapshot_date, ticker, current_price, units, market_value,
                invested_amount, total_return, total_return_pct, created_at
            )
            VALUES(1, '2026-04-15', '002611', 3, 10, 30, 20, 10, 50, '2026-04-15 16:00:00')
            """
        )
        con.commit()
    finally:
        con.close()

    store = AssetStore(tmp_path / "agent_assets.db")
    try:
        imported_user = import_dashboard_db(store, source_db, username="admin", replace=True)

        assert imported_user == "admin"
        assert store.snapshot_value("002611", dt.date(2026, 4, 16)) == pytest.approx(30.0)
    finally:
        store.close()


def test_render_json_output_wraps_reports():
    content = render_output(
        [
            {
                "generated_at": "2026-04-23T18:30:00",
                "markdown": "hello",
            }
        ],
        "json",
    )

    parsed = json.loads(content)
    assert parsed["count"] == 1
    assert parsed["reports"][0]["markdown"] == "hello"
