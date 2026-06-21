"""
布林带突破策略
"""

import pandas as pd
import numpy as np
from strategies.base import Strategy


class BollingerBandsStrategy(Strategy):
    """
    布林带均值回归策略

    规则：
    - 价格跌破下轨 → 买入（超卖反弹）
    - 价格突破上轨 → 卖出（超买回调）
    """

    def __init__(self, period: int = 20, std_dev: float = 2.0, name: str = None):
        super().__init__(name or f"布林带({period},{std_dev})")
        self.period = period
        self.std_dev = std_dev

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()

        # 计算布林带
        df["ma"] = df["close"].rolling(window=self.period).mean()
        df["std"] = df["close"].rolling(window=self.period).std()
        df["upper"] = df["ma"] + self.std_dev * df["std"]
        df["lower"] = df["ma"] - self.std_dev * df["std"]

        # 信号
        df["trade_signal"] = 0
        df.loc[df["close"] < df["lower"], "trade_signal"] = 1    # 跌破下轨买入
        df.loc[df["close"] > df["upper"], "trade_signal"] = -1   # 突破上轨卖出

        return df
