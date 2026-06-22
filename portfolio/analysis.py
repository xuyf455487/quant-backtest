"""
📊 技术分析信号计算模块
"""

import numpy as np
import pandas as pd


def calc_bollinger(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0):
    """布林带信号"""
    if len(df) < period:
        return {"signal": "数据不足", "detail": ""}

    close = df["close"].values
    ma = np.mean(close[-period:])
    std = np.std(close[-period:])
    upper = ma + std_dev * std
    lower = ma - std_dev * std
    current = close[-1]
    prev = close[-2] if len(close) > 1 else current

    if current < lower and prev >= lower:
        return {"signal": "🟢 买入", "detail": f"跌破下轨 {lower:.2f}"}
    if current > upper and prev <= upper:
        return {"signal": "🔴 减仓", "detail": f"突破上轨 {upper:.2f}"}
    if current < lower * 1.02:
        return {"signal": "🟡 关注加仓", "detail": f"接近下轨 {current:.2f}/{lower:.2f}"}
    return {"signal": "⚪ 持有", "detail": f"中轨 {ma:.2f}"}


def calc_rsi(df: pd.DataFrame, period: int = 14):
    """RSI 信号"""
    if len(df) < period + 1:
        return {"signal": "数据不足", "detail": ""}

    close = df["close"].values
    deltas = np.diff(close)
    gains = deltas.copy()
    losses = deltas.copy()
    gains[gains < 0] = 0
    losses[losses > 0] = 0
    losses = np.abs(losses)

    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        rsi = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

    if rsi < 30:
        return {"signal": "🟢 买入", "detail": f"RSI={rsi:.1f} 超卖"}
    elif rsi > 70:
        return {"signal": "🔴 减仓", "detail": f"RSI={rsi:.1f} 超买"}
    elif rsi < 40:
        return {"signal": "🟡 关注加仓", "detail": f"RSI={rsi:.1f} 偏低"}
    else:
        return {"signal": "⚪ 持有", "detail": f"RSI={rsi:.1f} 正常"}


def calc_macd(df: pd.DataFrame, fast=12, slow=26, signal=9):
    """MACD 金叉/死叉"""
    if len(df) < slow + signal:
        return {"signal": "数据不足", "detail": ""}

    close = df["close"].values
    ema_fast = pd.Series(close).ewm(span=fast, adjust=False).mean().values
    ema_slow = pd.Series(close).ewm(span=slow, adjust=False).mean().values
    macd_line = ema_fast - ema_slow
    macd_signal = pd.Series(macd_line).ewm(span=signal, adjust=False).mean().values
    macd_hist = macd_line - macd_signal

    curr_hist = macd_hist[-1]
    prev_hist = macd_hist[-2] if len(macd_hist) > 1 else 0

    if curr_hist > 0 and prev_hist <= 0:
        return {"signal": "🟢 金叉", "detail": "MACD上穿信号线"}
    elif curr_hist < 0 and prev_hist >= 0:
        return {"signal": "🔴 死叉", "detail": "MACD下穿信号线"}
    elif curr_hist > 0:
        return {"signal": "⚪ 多头", "detail": f"+{curr_hist:.4f}"}
    else:
        return {"signal": "⚪ 空头", "detail": f"{curr_hist:.4f}"}


def calc_change(df: pd.DataFrame) -> float:
    """最近一个交易日涨跌幅（%）"""
    if len(df) < 2:
        return 0.0
    return (df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2] * 100


def calc_full_return(df: pd.DataFrame, days: int = 20) -> float:
    """N个交易日收益率（%）"""
    if len(df) < days + 1:
        return 0.0
    return (df["close"].iloc[-1] - df["close"].iloc[-days]) / df["close"].iloc[-days] * 100


def analyze_asset(symbol: str, name: str, asset_type: str,
                  df: pd.DataFrame) -> dict:
    """分析单个资产，返回评估结果"""
    if df.empty:
        return {
            "symbol": symbol, "name": name, "error": "无数据",
            "close": None, "change": None,
            "bollinger": {"signal": "⚠️ 无数据", "detail": ""},
            "rsi": {"signal": "⚠️ 无数据", "detail": ""},
            "macd": {"signal": "⚠️ 无数据", "detail": ""},
        }

    close = df["close"].iloc[-1]
    change = calc_change(df)
    weekly_return = calc_full_return(df, 5)
    monthly_return = calc_full_return(df, 20)

    boll = calc_bollinger(df)
    rsi = calc_rsi(df)
    macd = calc_macd(df)

    scores = {"🟢 买入": 3, "🟢 金叉": 3, "🟡 关注加仓": 2,
              "🔴 减仓": -2, "🔴 死叉": -2}
    score = scores.get(boll["signal"], 0) + scores.get(rsi["signal"], 0) + scores.get(macd["signal"], 0)

    if score >= 5:
        advice = "✅ 强烈建议加仓"
    elif score >= 2:
        advice = "📈 建议加仓"
    elif score <= -3:
        advice = "⚠️ 建议减仓止盈"
    elif score <= -1:
        advice = "📉 建议观望/减仓"
    else:
        advice = "➡️ 继续持有"

    return {
        "symbol": symbol, "name": name,
        "close": round(float(close), 2) if close is not None else None,
        "change": round(change, 2),
        "weekly_return": round(weekly_return, 2),
        "monthly_return": round(monthly_return, 2),
        "bollinger": boll,
        "rsi": rsi,
        "macd": macd,
        "advice": advice,
        "score": score,
        "error": None,
    }
