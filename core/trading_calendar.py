"""交易日历模块

职责:
- 判断指定日期是否为交易日
- 获取市场开盘/收盘时间
- 支持 A 股、港股、美股市场

借鉴来源: daily_stock_analysis 项目
"""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Optional, Set
import logging

from . import tushare_provider

logger = logging.getLogger(__name__)


class Market(str, Enum):
    """市场类型"""
    A_SHARE = "a_share"      # A 股
    HK_SHARE = "hk_share"    # 港股
    US_SHARE = "us_share"    # 美股


class TradingCalendar:
    """交易日历"""

    # A 股固定节假日（需要根据实际每年更新）
    # 格式：YYYY-MM-DD
    CHINA_HOLIDAYS_2026 = {
        # 元旦
        "2026-01-01", "2026-01-02", "2026-01-03",
        # 春节
        "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20", "2026-02-21",
        "2026-02-22", "2026-02-23", "2026-02-24",
        # 清明节
        "2026-04-04", "2026-04-05", "2026-04-06",
        # 劳动节
        "2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05",
        # 端午节
        "2026-06-19", "2026-06-20", "2026-06-21",
        # 中秋节
        "2026-09-25", "2026-09-26", "2026-09-27",
        # 国庆节
        "2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04",
        "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08",
    }

    # 港股节假日（部分与 A 股不同）
    HK_HOLIDAYS_2026 = {
        *CHINA_HOLIDAYS_2026,
        # 耶稣受难节
        "2026-04-03",
        # 复活节星期一
        "2026-04-06",
        # 佛诞
        "2026-05-25",
        # 国庆节后
        "2026-10-09",
        # 重阳节
        "2026-10-21",
        # 圣诞节
        "2026-12-25", "2026-12-26", "2026-12-27",
    }

    # 美股节假日
    US_HOLIDAYS_2026 = {
        # 元旦
        "2026-01-01",
        # 马丁路德金日
        "2026-01-19",
        # 华盛顿诞辰
        "2026-02-16",
        # 耶稣受难节
        "2026-04-03",
        # 亡兵纪念日
        "2026-05-25",
        # 独立日
        "2026-07-03",  # 7 月 4 日周六，提前到周五
        # 劳动节
        "2026-09-07",
        # 感恩节
        "2026-11-26",
        # 圣诞节
        "2026-12-25",
    }

    def __init__(self):
        """初始化交易日历"""
        logger.info("交易日历初始化完成")

    def _normalize_market(self, market: Market | str) -> Market:
        if isinstance(market, Market):
            return market
        return Market(str(market).lower())

    def _get_holidays(self, market: Market, year: int) -> Set[str]:
        """获取指定市场的节假日"""
        market = self._normalize_market(market)
        if year == 2026:
            if market == Market.A_SHARE:
                return self.CHINA_HOLIDAYS_2026
            elif market == Market.HK_SHARE:
                return self.HK_HOLIDAYS_2026
            elif market == Market.US_SHARE:
                return self.US_HOLIDAYS_2026
        # 默认返回 A 股节假日（其他年份可扩展）
        return self.CHINA_HOLIDAYS_2026

    def is_trading_day(
        self,
        date: Optional[datetime.date] = None,
        market: Market | str = Market.A_SHARE,
        force_check: bool = False,
    ) -> bool:
        """
        判断指定日期是否为交易日

        Args:
            date: 日期，None 表示今天
            market: 市场类型
            force_check: 是否强制执行（跳过节假日检查）

        Returns:
            是否为交易日
        """
        if date is None:
            date = datetime.date.today()
        market = self._normalize_market(market)

        # 格式化日期
        date_str = date.strftime("%Y-%m-%d")

        # 强制运行时，跳过节假日检查
        if force_check:
            logger.info(f"强制执行：{date_str} ({market.value})")
            return True

        # A 股优先使用 Tushare 交易日历，提高节假日准确性。
        if market == Market.A_SHARE:
            remote_result = tushare_provider.is_a_share_trading_day(date)
            if remote_result is not None:
                return remote_result

        # 1. 检查周末
        if date.weekday() >= 5:  # 5=周六，6=周日
            logger.debug(f"{date_str} 是周末")
            return False

        # 2. 检查节假日
        holidays = self._get_holidays(market, date.year)
        if date_str in holidays:
            logger.debug(f"{date_str} 是节假日 ({market.value})")
            return False

        return True

    def is_a_share_trading_day(
        self,
        date: Optional[datetime.date] = None,
        force_check: bool = False,
    ) -> bool:
        """判断是否为 A 股交易日"""
        return self.is_trading_day(date, Market.A_SHARE, force_check)

    def get_next_trading_day(
        self,
        from_date: Optional[datetime.date] = None,
        market: Market | str = Market.A_SHARE,
        days: int = 1,
    ) -> datetime.date:
        """
        获取下一个交易日

        Args:
            from_date: 起始日期，None 表示今天
            market: 市场类型
            days: 向前推多少个交易日

        Returns:
            下一个交易日
        """
        if from_date is None:
            from_date = datetime.date.today()
        market = self._normalize_market(market)

        if market == Market.A_SHARE:
            remote_result = tushare_provider.get_next_a_share_trading_day(from_date, days)
            if remote_result is not None:
                return remote_result

        current = from_date
        found = 0

        while found < days:
            current += datetime.timedelta(days=1)
            if self.is_trading_day(current, market):
                found += 1

        return current

    def get_market_hours(self, market: Market | str) -> dict:
        """
        获取市场交易时间

        Args:
            market: 市场类型

        Returns:
            包含开盘/收盘时间的字典
        """
        market = self._normalize_market(market)
        if market == Market.A_SHARE:
            return {
                "open": "09:30",
                "close": "15:00",
                "morning_break": "11:30",
                "afternoon_start": "13:00",
            }
        elif market == Market.HK_SHARE:
            return {
                "open": "09:30",
                "close": "16:00",
                "morning_break": "12:00",
                "afternoon_start": "13:00",
            }
        elif market == Market.US_SHARE:
            return {
                "open": "09:30",
                "close": "16:00",
                # 美股午间不休市
            }
        return {}

    def should_skip_execution(
        self,
        market: Market | str = Market.A_SHARE,
        force_run: bool = False,
    ) -> bool:
        """
        判断是否应该跳过执行（用于定时任务）

        Args:
            market: 市场类型
            force_run: 是否强制运行

        Returns:
            True 表示应该跳过
        """
        if force_run:
            return False
        market = self._normalize_market(market)

        today = datetime.date.today()
        is_trading = self.is_trading_day(today, market)

        if not is_trading:
            logger.info(f"今天 ({today}) 不是 {market.value} 交易日，跳过执行")
            return True

        return False


# 全局交易日历实例
_calendar: Optional[TradingCalendar] = None


def get_trading_calendar() -> TradingCalendar:
    """获取交易日历实例（单例模式）"""
    global _calendar
    if _calendar is None:
        _calendar = TradingCalendar()
    return _calendar


def is_trading_day(
    date: Optional[datetime.date] = None,
    market: str = "a_share",
    force_check: bool = False,
) -> bool:
    """便捷函数：判断是否为交易日"""
    market_enum = Market(market.lower())
    return get_trading_calendar().is_trading_day(date, market_enum, force_check)


def should_skip_execution(
    market: str = "a_share",
    force_run: bool = False,
) -> bool:
    """便捷函数：判断是否应该跳过执行"""
    return get_trading_calendar().should_skip_execution(Market(market.lower()), force_run)
