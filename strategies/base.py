"""
策略基类 — 所有策略继承此类
"""

import pandas as pd
from abc import ABC, abstractmethod


class Strategy(ABC):
    """策略基类"""

    def __init__(self, name: str = None):
        self.name = name or self.__class__.__name__
        self.data = None
        self.signals = None

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号

        参数:
            data: 行情数据 (columns: date, open, high, low, close, volume)

        返回:
            带 signals 列的 DataFrame:
              signal=1 → 买入, signal=-1 → 卖出, signal=0 → 持有
        """
        pass

    def __str__(self):
        return self.name
