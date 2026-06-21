"""
MACD 趋势跟踪策略
"""

import pandas as pd
import numpy as np
from strategies.base import Strategy


class MACDStrategy(Strategy):
    """
    MACD 金叉死叉策略

    规则：
    - MACD 线上穿信号线（金叉）→ 买入
    - MACD 线下穿信号线（死叉）→ 卖出
    """

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9, name: str = None):
        super().__init__(name or f"MACD({fast},{slow},{signal})")
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()

        # 计算 MACD
        ema_fast = df["close"].ewm(span=self.fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=self.slow, adjust=False).mean()
        df["macd"] = ema_fast - ema_slow
        df["macd_signal"] = df["macd"].ewm(span=self.signal, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        # 金叉/死叉信号
        df["trade_signal"] = 0
        df["prev_hist"] = df["macd_hist"].shift(1)
        df.loc[(df["macd_hist"] > 0) & (df["prev_hist"] <= 0), "trade_signal"] = 1   # 金叉
        df.loc[(df["macd_hist"] < 0) & (df["prev_hist"] >= 0), "trade_signal"] = -1  # 死叉

        return df
