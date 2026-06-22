"""
示例策略 — 双均线交叉策略（最经典的回测入门策略）
"""

import pandas as pd
import numpy as np
from strategies.base import Strategy


class MovingAverageCrossStrategy(Strategy):
    """
    双均线交叉策略

    规则：
    - 短期均线上穿长期均线 → 买入信号
    - 短期均线下穿长期均线 → 卖出信号
    """

    def __init__(self, short_window: int = 5, long_window: int = 20, name: str = None):
        if short_window <= 0 or long_window <= 0:
            raise ValueError("short_window and long_window must be positive")
        if short_window >= long_window:
            raise ValueError("short_window must be smaller than long_window")
        super().__init__(name)
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()

        # 计算短期和长期均线
        df["ma_short"] = df["close"].rolling(window=self.short_window).mean()
        df["ma_long"] = df["close"].rolling(window=self.long_window).mean()

        # 生成信号：1 买入, -1 卖出, 0 持有
        df["signal"] = 0
        df.loc[df["ma_short"] > df["ma_long"], "signal"] = 1

        # 取信号变化点（交叉点才是真正信号）
        df["position"] = df["signal"].diff()

        # 映射为交易信号
        df["trade_signal"] = 0
        df.loc[df["position"] == 1, "trade_signal"] = 1   # 金叉买入
        df.loc[df["position"] == -1, "trade_signal"] = -1  # 死叉卖出

        return df
