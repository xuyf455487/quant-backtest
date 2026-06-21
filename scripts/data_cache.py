"""
数据缓存层 — SQLite 本地缓存 + 增量更新

自动缓存从 akshare/yfinance 获取的数据，下次相同请求直接读本地。
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from functools import wraps
from datetime import datetime, timedelta


CACHE_DB = Path(__file__).parent.parent / "data" / "cache.db"


def init_cache():
    """初始化缓存数据库"""
    CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CACHE_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_data (
            symbol TEXT,
            date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            source TEXT,
            updated_at TEXT,
            PRIMARY KEY (symbol, date)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache_meta (
            symbol TEXT PRIMARY KEY,
            last_fetch TEXT,
            data_start TEXT,
            data_end TEXT,
            rows INTEGER
        )
    """)
    conn.commit()
    conn.close()


def get_cached_data(symbol: str, start_date: str, end_date: str, max_age_days: int = 1) -> pd.DataFrame:
    """
    从缓存获取数据

    返回: DataFrame 或 None（缓存不存在/过期）
    """
    conn = sqlite3.connect(str(CACHE_DB))

    # 检查元数据
    meta = conn.execute(
        "SELECT last_fetch, data_start, data_end FROM cache_meta WHERE symbol = ?",
        (symbol,)
    ).fetchone()

    if meta is None:
        conn.close()
        return None

    last_fetch = pd.Timestamp(meta[0])
    data_start = meta[1]
    data_end = meta[2]

    # 检查是否过期
    if (datetime.now() - last_fetch) > timedelta(days=max_age_days):
        conn.close()
        return None

    # 检查是否覆盖请求范围
    req_start = pd.Timestamp(start_date)
    req_end = pd.Timestamp(end_date)
    cache_start = pd.Timestamp(data_start)
    cache_end = pd.Timestamp(data_end)

    if req_start < cache_start or req_end > cache_end:
        conn.close()
        return None

    # 读取缓存
    df = pd.read_sql_query(
        "SELECT date, open, high, low, close, volume FROM market_data "
        "WHERE symbol = ? AND date >= ? AND date <= ? "
        "ORDER BY date",
        conn, params=(symbol, start_date, end_date)
    )

    conn.close()

    if df.empty:
        return None

    df["date"] = pd.to_datetime(df["date"])
    return df


def save_to_cache(symbol: str, df: pd.DataFrame, source: str = "akshare"):
    """保存数据到缓存"""
    init_cache()
    conn = sqlite3.connect(str(CACHE_DB))

    # 确保有标准列名
    data = df.copy()
    data["symbol"] = symbol
    data["source"] = source
    data["updated_at"] = datetime.now().isoformat()

    # 逐行 upsert
    for _, row in data.iterrows():
        conn.execute("""
            INSERT OR REPLACE INTO market_data
            (symbol, date, open, high, low, close, volume, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            symbol,
            row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], "strftime") else str(row["date"]),
            float(row.get("open", 0)),
            float(row.get("high", 0)),
            float(row.get("low", 0)),
            float(row.get("close", 0)),
            float(row.get("volume", 0)),
            source,
            datetime.now().isoformat(),
        ))

    conn.commit()

    # 更新元数据
    dates = data["date"] if "date" in data.columns else data["净值日期"]
    conn.execute("""
        INSERT OR REPLACE INTO cache_meta
        (symbol, last_fetch, data_start, data_end, rows)
        VALUES (?, ?, ?, ?, ?)
    """, (
        symbol,
        datetime.now().isoformat(),
        str(pd.Timestamp(dates.min()).date()),
        str(pd.Timestamp(dates.max()).date()),
        len(data),
    ))

    conn.commit()
    conn.close()


def clear_cache(symbol: str = None):
    """清除缓存"""
    import os
    conn = sqlite3.connect(str(CACHE_DB))
    if symbol:
        conn.execute("DELETE FROM market_data WHERE symbol = ?", (symbol,))
        conn.execute("DELETE FROM cache_meta WHERE symbol = ?", (symbol,))
    else:
        conn.execute("DELETE FROM market_data")
        conn.execute("DELETE FROM cache_meta")
    conn.commit()
    conn.close()


def cache_data(max_age_days: int = 1):
    """
    装饰器：自动缓存数据获取函数的结果

    用法:
        @cache_data(max_age_days=1)
        def get_stock_data(symbol, start_date, end_date):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(symbol, start_date, end_date, *args, **kwargs):
            # 尝试读缓存
            cached = get_cached_data(symbol, start_date, end_date, max_age_days)
            if cached is not None:
                return cached

            # 调用原函数
            df = func(symbol, start_date, end_date, *args, **kwargs)

            # 保存到缓存
            if df is not None and not df.empty:
                source = kwargs.get("source", "akshare")
                save_to_cache(symbol, df, source)

            return df
        return wrapper
    return decorator
