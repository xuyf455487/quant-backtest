"""
定投策略 — 定期定额投资（Dollar-Cost Averaging）
"""

import pandas as pd
from strategies.base import Strategy


class DCAStrategy(Strategy):
    """
    定期定额定投策略 (Dollar-Cost Averaging)

    每月第一个交易日买入固定金额的资产。
    不卖出，长期持有。
    """

    def __init__(self, monthly_invest: float = 500, name: str = None):
        super().__init__(name or f"DCA(${monthly_invest}/月)")
        self.monthly_invest = monthly_invest

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df["date"] = pd.to_datetime(df["date"])

        # 标记每月第一个交易日
        df["year_month"] = df["date"].dt.to_period("M")
        df["trade_signal"] = 0

        # 每个月的第一个交易日设为买入信号
        first_trade_dates = df.groupby("year_month")["date"].transform("first")
        df.loc[df["date"] == first_trade_dates, "trade_signal"] = 1

        return df.drop(columns=["year_month"])
