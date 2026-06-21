"""
数据获取模块 — 支持 A股/基金/美股

数据源优先级：
1. akshare（A股、基金、期货）
2. yfinance（美股、港股）
"""

import pandas as pd
from pathlib import Path


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
        df = df.rename(columns={
            "日期": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
        })
        df["date"] = pd.to_datetime(df["date"])
        return df[["date", "open", "high", "low", "close", "volume"]]
    else:
        # 基金代码
        df = ak.fund_open_fund_info_em(
            symbol=symbol,
            indicator="单位净值走势",
        )
        df = df.rename(columns={
            "净值日期": "date",
            "单位净值": "close",
        })
        df["date"] = pd.to_datetime(df["date"])
        return df[["date", "close"]]


def _get_yfinance_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """通过 yfinance 获取美股/港股数据"""
    import yfinance as yf

    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start_date, end=end_date)
    df = df.reset_index()
    df.columns = [c.lower() for c in df.columns]
    return df[["date", "open", "high", "low", "close", "volume"]]
