"""
931574 中证港股科技指数月定投回测脚本

使用跟踪该指数的 159747 南方中证香港科技ETF 的净值数据
"""

import akshare as ak
import pandas as pd


def monthly_dca_backtest(fund_code, fund_name, monthly_amount=500, 
                          start_date="2018-01-01", end_date="2025-12-31"):
    """
    基金月定投回测
    """
    df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
    df["净值日期"] = pd.to_datetime(df["净值日期"])
    df = df.sort_values("净值日期").reset_index(drop=True)
    
    s, e = pd.Timestamp(start_date), pd.Timestamp(end_date)
    df = df[(df["净值日期"] >= s) & (df["净值日期"] <= e)].reset_index(drop=True)
    
    if len(df) == 0:
        return None
    
    invested = 0
    shares = 0.0
    trades = []
    
    for i in range(len(df)):
        date = df.iloc[i]["净值日期"]
        nav = df.iloc[i]["单位净值"]
        ym = date.to_period("M")
        if len(trades) == 0 or ym != trades[-1]["ym"]:
            s = monthly_amount / nav
            shares += s
            invested += monthly_amount
            trades.append({"date": date, "nav": nav, "ym": ym, 
                          "inv": invested, "val": shares * nav})
    
    final_val = shares * df["单位净值"].iloc[-1]
    years = (df["净值日期"].iloc[-1] - df["净值日期"].iloc[0]).days / 365.25
    total_ret = (final_val - invested) / invested
    ann_ret = (1 + total_ret) ** (1 / years) - 1
    
    return {
        "fund": fund_name,
        "code": fund_code,
        "start": df["净值日期"].iloc[0],
        "end": df["净值日期"].iloc[-1],
        "years": round(years, 1),
        "invested": invested,
        "final_value": round(final_val, 2),
        "total_return": total_ret,
        "annual_return": ann_ret,
        "trade_count": len(trades),
        "trades": trades,
    }


if __name__ == "__main__":
    import sys
    
    code = sys.argv[1] if len(sys.argv) > 1 else "159747"
    name = sys.argv[2] if len(sys.argv) > 2 else "中证香港科技ETF"
    amount = float(sys.argv[3]) if len(sys.argv) > 3 else 500
    
    print(f"\n⏳ 获取 {name} 数据...")
    r = monthly_dca_backtest(code, name, amount)
    
    if r:
        print("=" * 60)
        print(f"📊 {r['fund']} ({r['code']}) 月定投回测")
        print("=" * 60)
        print(f"  周期:  {r['start'].date()} ~ {r['end'].date()} ({r['years']}年)")
        print(f"  每月:  ¥{amount:,.0f}")
        print("-" * 60)
        print(f"  总投入: ¥{r['invested']:>8,.2f}")
        print(f"  最终值: ¥{r['final_value']:>8,.2f}")
        print(f"  总收益: ¥{r['final_value'] - r['invested']:>8,.2f}")
        print(f"  收益率: {r['total_return']:>+8.2%}")
        print(f"  年化:   {r['annual_return']:>+8.2%}")
        print(f"  定投:   {r['trade_count']} 次")
        print("=" * 60)
        
        df_t = pd.DataFrame(r['trades'])
        print(f"\n📅 年度:")
        for y in range(r['start'].year, r['end'].year + 1):
            yr = df_t[df_t["date"].dt.year <= y]
            if not yr.empty:
                last = yr.iloc[-1]
                ret = (last["val"] - last["inv"]) / last["inv"]
                print(f"  {y}: ¥{last['inv']:<7,.0f} → ¥{last['val']:<9,.2f} ({ret:>+.2%})")
    else:
        print(f"❌ {code}: 在指定时间范围内无数据")
