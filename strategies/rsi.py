"""
RSI 反转策略
"""

import pandas as pd
import numpy as np
from strategies.base import Strategy


class RSIStrategy(Strategy):
    """
    RSI 超买超卖反转策略

    规则：
    - RSI < oversold_threshold → 买入（超卖反弹）
    - RSI > overbought_threshold → 卖出（超买回调）
    """

    def __init__(self, period: int = 14, oversold: int = 30, overbought: int = 70, name: str = None):
        super().__init__(name or f"RSI({period})")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()

        # 计算 RSI
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))

        # 信号
        df["trade_signal"] = 0
        was_oversold = df["rsi"].shift(1) < self.oversold
        is_oversold = df["rsi"] < self.oversold
        was_overbought = df["rsi"].shift(1) > self.overbought
        is_overbought = df["rsi"] > self.overbought
        df.loc[is_oversold & ~was_oversold.fillna(False), "trade_signal"] = 1
        df.loc[is_overbought & ~was_overbought.fillna(False), "trade_signal"] = -1

        return df
