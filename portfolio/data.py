"""
📊 行情数据获取模块
"""

import pandas as pd
from pathlib import Path


def fetch_hist(symbol: str, days: int = 60, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """
    获取历史行情数据
    返回 columns: [date, open, high, low, close, volume]
    """
    import akshare as ak

    code = symbol[2:] if symbol.startswith(("sh", "sz", "bj")) else symbol

    if start_date and end_date:
        pass  # use as-is
    else:
        from datetime import datetime, timedelta
        end = datetime.now()
        start = end - timedelta(days=days * 2)
        start_date = start.strftime("%Y%m%d")
        end_date = end.strftime("%Y%m%d")

    if symbol.startswith(("sh", "sz", "bj")):
        return _fetch_a_stock(code, start_date, end_date, days, full_symbol=symbol)
    else:
        return _fetch_etf_fund(code, start_date, end_date, days)


def _fetch_a_stock(code: str, start_date: str, end_date: str, days: int, full_symbol: str = None) -> pd.DataFrame:
    """获取A股个股行情"""
    import akshare as ak

    try:
        df = ak.stock_zh_a_hist(
            symbol=code, period="daily",
            start_date=start_date, end_date=end_date, adjust="qfq",
        )
    except Exception:
        df = _fetch_stock_fallback(code, days, full_symbol or code)
        return df

    df = df.rename(columns={
        "日期": "date", "开盘": "open", "最高": "high",
        "最低": "low", "收盘": "close", "成交量": "volume",
    })
    df["date"] = pd.to_datetime(df["date"])
    df = df[["date", "open", "high", "low", "close", "volume"]]
    df = df.sort_values("date").tail(days).reset_index(drop=True)
    return df


def _fetch_stock_fallback(code: str, days: int, full_symbol: str = None) -> pd.DataFrame:
    """备用接口：使用新浪财经接口，避免东方财富接口的限流"""
    import requests
    from datetime import datetime

    # full_symbol 带 sh/sz 前缀（如 sh600519），code 是纯数字
    sym_for_sina = full_symbol or code

    # 新浪免费接口：用日K线
    url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={sym_for_sina}&scale=240&ma=no&datalen={days * 2}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
    except Exception:
        # 换用新浪备用接口
        url = f"http://quotes.money.163.com/service/chddata.html?code=0{code}&start=20250101&end=20261231"
        resp = requests.get(url, timeout=10)
        import io
        df = pd.read_csv(io.StringIO(resp.text), encoding="gbk")
        df = df.rename(columns={
            "日期": "date", "开盘价": "open", "最高价": "high",
            "最低价": "low", "收盘价": "close", "成交量": "volume",
        })
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        return df[["date", "open", "high", "low", "close", "volume"]].tail(days).reset_index(drop=True)

    if not data:
        raise ConnectionError("无可用的历史数据")

    rows = []
    for d in data:
        rows.append({
            "date": pd.to_datetime(d["day"]),
            "open": float(d["open"]),
            "high": float(d["high"]),
            "low": float(d["low"]),
            "close": float(d["close"]),
            "volume": float(d.get("volume", 0)),
        })
    df = pd.DataFrame(rows)
    df = df.sort_values("date")
    return df.tail(days).reset_index(drop=True)


def _fetch_etf_fund(code: str, start_date: str, end_date: str, days: int) -> pd.DataFrame:
    """获取ETF/基金行情"""
    import akshare as ak

    # ETF 行情接口
    for _ in range(2):
        try:
            df = ak.fund_etf_hist_em(
                symbol=code, period="daily",
                start_date=start_date, end_date=end_date, adjust="qfq",
            )
            df = df.rename(columns={
                "日期": "date", "开盘": "open", "最高": "high",
                "最低": "low", "收盘": "close", "成交量": "volume",
            })
            break
        except Exception:
            # 试试净值接口
            try:
                df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
                df = df.rename(columns={"净值日期": "date", "单位净值": "close"})
                df["open"] = df["close"]
                df["high"] = df["close"]
                df["low"] = df["close"]
                df["volume"] = 0
                break
            except Exception:
                raise

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").tail(days).reset_index(drop=True)
    return df
