"""
数据获取模块 — 支持 A股/基金/美股

数据源优先级：
1. akshare（A股、基金、期货）
2. yfinance（美股、港股）
"""

import pandas as pd
from pathlib import Path


OHLCV_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """
    将不同数据源的行情字段统一为 date/open/high/low/close/volume。
    只有净值或收盘价的数据会用 close 补齐 OHLC，并将 volume 设为 0。
    """
    column_map = {
        "日期": "date",
        "净值日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "单位净值": "close",
        "成交量": "volume",
        "Date": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    }
    normalized = df.rename(columns=column_map).copy()
    normalized.columns = [str(c).lower() for c in normalized.columns]

    if "date" not in normalized.columns:
        raise ValueError("行情数据缺少 date 列")
    if "close" not in normalized.columns:
        raise ValueError("行情数据缺少 close 列")

    normalized["date"] = pd.to_datetime(normalized["date"])
    for col in ("open", "high", "low"):
        if col not in normalized.columns:
            normalized[col] = normalized["close"]
    if "volume" not in normalized.columns:
        normalized["volume"] = 0

    normalized = normalized[OHLCV_COLUMNS].sort_values("date").reset_index(drop=True)
    return normalized


def get_stock_data(
    symbol: str,
    start_date: str = "2020-01-01",
    end_date: str = None,
    source: str = "akshare",
) -> pd.DataFrame:
    """
    获取股票/基金行情数据

    参数:
        symbol: 代码 (A股: 'sh600519', 基金: '000001', 美股: 'AAPL')
        start_date: 起始日期
        end_date: 结束日期 (默认今天)
        source: 数据源 ('akshare' | 'yfinance')

    返回:
        DataFrame columns: [date, open, high, low, close, volume]
    """
    if end_date is None:
        from datetime import datetime
        end_date = datetime.now().strftime("%Y-%m-%d")

    if source == "akshare":
        return _get_akshare_data(symbol, start_date, end_date)
    elif source == "yfinance":
        return _get_yfinance_data(symbol, start_date, end_date)
    else:
        raise ValueError(f"不支持的数据源: {source}")


def _get_akshare_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """通过 akshare 获取 A股/基金数据"""
    import akshare as ak

    # 自动判断类型
    if symbol.startswith(("sh", "sz", "bj")):
        df = ak.stock_zh_a_hist(
            symbol=symbol[2:],
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",  # 前复权
        )
        return normalize_ohlcv(df)
    else:
        # 基金代码
        df = ak.fund_open_fund_info_em(
            symbol=symbol,
            indicator="单位净值走势",
        )
        return normalize_ohlcv(df)


def _get_yfinance_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """通过 yfinance 获取美股/港股数据"""
    import yfinance as yf

    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start_date, end=end_date)
    df = df.reset_index()
    return normalize_ohlcv(df)
