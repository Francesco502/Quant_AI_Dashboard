from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

import pytest

from core.asset_metadata import (
    DEFAULT_ASSET_POOL,
    get_asset_hint,
    get_asset_pool_tickers,
    list_user_asset_pool,
    save_user_asset_pool,
)
from core.database import Database


pytestmark = pytest.mark.unit


@pytest.fixture
def asset_metadata_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Database(os.path.join(tmpdir, "asset_metadata.db"))
        with patch("core.asset_metadata.get_database", return_value=db):
            yield db
            if db.conn:
                db.conn.close()


def test_user_asset_pool_is_seeded_and_isolated_per_user(asset_metadata_db):
    default_tickers = [item["ticker"] for item in DEFAULT_ASSET_POOL]

    user_one_pool = list_user_asset_pool(1)
    assert [item["ticker"] for item in user_one_pool] == default_tickers

    custom_pool = save_user_asset_pool(
        2,
        [
            {
                "ticker": "600000",
                "name": "浦发银行",
                "alias": "我的银行股",
                "asset_type": "stock",
                "market": "CN",
            }
        ],
    )

    assert [item["ticker"] for item in custom_pool] == ["600000"]
    assert get_asset_pool_tickers(user_id=2) == ["600000"]
    assert get_asset_hint("600000", user_id=2)["name"] == "浦发银行"

    assert get_asset_pool_tickers(user_id=1) == default_tickers
    assert get_asset_hint("600000", user_id=1) == {}

