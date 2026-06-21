"""
模拟数据生成器 — 无需网络即可生成逼真的A股行情数据

用于开发和演示，生成的数据在统计上与真实A股行情类似。
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def generate_stock_data(
    symbol: str = "sh600519",
    days: int = 1000,
    start_price: float = 100.0,
    volatility: float = 0.02,
    seed: int = None,
) -> pd.DataFrame:
    """
    生成逼真的股票模拟行情数据

    参数:
        symbol: 股票代码
        days: 交易天数
        start_price: 起始价格
        volatility: 日波动率
        seed: 随机种子（固定后可复现）

    返回:
        DataFrame columns: [date, open, high, low, close, volume]
    """
    if seed is not None:
        np.random.seed(seed)

    # 生成日期（跳过周末）
    dates = []
    d = pd.Timestamp("2020-01-01")
    while len(dates) < days:
        if d.weekday() < 5:  # 周一到周五
            dates.append(d)
        d += timedelta(days=1)

    dates = dates[:days]

    # 生成价格序列（带趋势和波动）
    returns = np.random.randn(days) * volatility

    # 加入微弱上升趋势（模拟A股长期波动）
    trend = np.linspace(0, 0.15, days) / days
    returns = returns + trend

    # 加入跳跃（模拟跳空）
    gap_days = np.random.choice(range(days), size=int(days * 0.02), replace=False)
    for gd in gap_days:
        returns[gd] += np.random.randn() * volatility * 3

    price = start_price
    closes = []
    for r in returns:
        price = price * (1 + r)
        price = max(price, start_price * 0.3)  # 防止归零
        closes.append(price)

    closes = np.array(closes)

    # 生成 OHLC
    data = pd.DataFrame({
        "date": dates,
        "open": closes * (1 + np.random.randn(days) * 0.004),
        "high": closes * (1 + np.abs(np.random.randn(days)) * 0.012),
        "low": closes * (1 - np.abs(np.random.randn(days)) * 0.012),
        "close": closes,
        "volume": np.random.lognormal(mean=12, sigma=1.5, size=days).astype(int),
    })

    # 确保 high >= open/close, low <= open/close
    data["high"] = data[["open", "close", "high"]].max(axis=1)
    data["low"] = data[["open", "close", "low"]].min(axis=1)

    data["symbol"] = symbol
    return data


def generate_fund_data(
    fund_code: str = "005561",
    days: int = 1500,
    start_nav: float = 1.0,
    volatility: float = 0.008,
    seed: int = 42,
) -> pd.DataFrame:
    """
    生成基金净值模拟数据（类似红利低波的走势）
    """
    if seed is not None:
        np.random.seed(seed)

    dates = []
    d = pd.Timestamp("2018-04-01")
    while len(dates) < days:
        if d.weekday() < 5:
            dates.append(d)
        d += timedelta(days=1)

    dates = dates[:days]

    # 基金净值一般波动较小，有长期向上趋势
    returns = np.random.randn(days) * volatility + 0.0005
    nav = start_nav
    navs = []
    for r in returns:
        nav = nav * (1 + r)
        nav = max(nav, 0.5)
        navs.append(round(nav, 4))

    return pd.DataFrame({
        "净值日期": dates,
        "单位净值": navs,
        "基金代码": fund_code,
    })


STRATEGY_DESCRIPTIONS = {
    "ma_cross": {
        "name": "双均线交叉",
        "desc": "短期均线上穿长期均线买入，下穿卖出。经典的顺势跟踪策略。",
        "params": {"short_window": 5, "long_window": 20},
    },
    "rsi": {
        "name": "RSI反转",
        "desc": "RSI低于30超卖买入，高于70超买卖出。捕捉均值回归。",
        "params": {"period": 14, "oversold": 30, "overbought": 70},
    },
    "macd": {
        "name": "MACD金叉死叉",
        "desc": "MACD线上穿信号线买入，下穿卖出。最常用的趋势指标。",
        "params": {"fast": 12, "slow": 26, "signal": 9},
    },
    "bollinger": {
        "name": "布林带突破",
        "desc": "价格跌破下轨买入，突破上轨卖出。基于波动率的均值回归策略。",
        "params": {"period": 20, "std_dev": 2.0},
    },
}


def get_demo_result():
    """
    生成一个完整的演示回测结果（无需网络）
    返回: (data_dict, result_dict, strategy_name)
    """
    data = generate_stock_data("sh600519", days=500, start_price=180, seed=42)

    from strategies.ma_cross import MovingAverageCrossStrategy
    from backtest.engine import run_backtest

    strategy = MovingAverageCrossStrategy(short_window=5, long_window=20)
    result = run_backtest(data, strategy, initial_capital=100000)

    return data, result, "双均线交叉(MA5/20)"
