"""
标普500定投回测 — 每月定投 SPY，统计历年收益
"""

import pandas as pd
import numpy as np
import yfinance as yf


def dca_backtest(
    symbol: str = "SPY",
    monthly_invest: float = 500,
    start_date: str = "2010-01-01",
    end_date: str = "2025-06-20",
):
    """
    执行定投回测

    参数:
        symbol: ETF代码 (SPY=标普500, QQQ=纳斯达克, VTI=全市场)
        monthly_invest: 每月定投金额 (USD)
        start_date: 起始日期
        end_date: 结束日期

    返回:
        (result_dict, trade_log_df)
    """
    # 获取数据
    ticker = yf.Ticker(symbol)
    hist = ticker.history(start=start_date, end=end_date)
    df = hist[["Close"]].copy()
    df.index = pd.to_datetime(df.index.date)

    # 定投模拟
    total_invested = 0
    total_shares = 0.0
    trade_log = []

    current = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    while current <= end:
        month_start = current.replace(day=1)
        available = df[(df.index >= month_start) & (df.index <= end)]

        if not available.empty:
            buy_date = available.index[0]
            price = df.loc[buy_date, "Close"]
            shares = monthly_invest / price
            total_shares += shares
            total_invested += monthly_invest

            trade_log.append({
                "date": buy_date,
                "price": round(price, 2),
                "shares": round(shares, 4),
                "cumulative_invested": total_invested,
                "cumulative_value": round(total_shares * price, 2),
            })

        current = (current.replace(day=1) + pd.DateOffset(months=1))

    # 最终结果
    final_price = df.loc[df.index <= end, "Close"].iloc[-1]
    final_value = total_shares * final_price

    years = (end - pd.Timestamp(start_date)).days / 365.25
    total_return = (final_value - total_invested) / total_invested
    annual_return = (1 + total_return) ** (1 / years) - 1

    result = {
        "标的": symbol,
        "周期": f"{start_date} ~ {end_date} ({years:.1f}年)",
        "每月定投": monthly_invest,
        "总投入": total_invested,
        "最终市值": round(final_value, 2),
        "总收益": round(final_value - total_invested, 2),
        "总收益率": total_return,
        "年化收益率": annual_return,
    }

    return result, pd.DataFrame(trade_log)


def print_result(result):
    """打印回测结果"""
    print("=" * 60)
    print(f"📊 {result['标的']} 定投回测")
    print("=" * 60)
    print(f"  周期:     {result['周期']}")
    print(f"  每月定投: ${result['每月定投']:,.2f}")
    print("-" * 60)
    print(f"  总投入:   ${result['总投入']:,.2f}")
    print(f"  最终市值: ${result['最终市值']:,.2f}")
    print(f"  总收益:   ${result['总收益']:,.2f}")
    print(f"  总收益率: {result['总收益率']:.2%}")
    print(f"  年化收益率: {result['年化收益率']:.2%}")
    print("=" * 60)


if __name__ == "__main__":
    import sys

    symbol = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    amount = float(sys.argv[2]) if len(sys.argv) > 2 else 500

    print(f"\n⏳ 正在获取 {symbol} 数据并进行定投回测...\n")
    result, trades = dca_backtest(symbol=symbol, monthly_invest=amount)
    print_result(result)
