
import akshare as ak
import pandas as pd
import numpy as np

def weekly_dca_backtest(fund_code, fund_name, weekly_amount=500, 
                        start_date="2016-06-17", end_date="2025-08-01"):
    """
    基金周定投回测
    
    参数:
        fund_code: 基金/ETF代码
        fund_name: 基金名称
        weekly_amount: 每周定投金额
        start_date: 起始日期
        end_date: 结束日期
    """
    df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
    df["净值日期"] = pd.to_datetime(df["净值日期"])
    df = df.sort_values("净值日期").reset_index(drop=True)
    
    s = pd.Timestamp(start_date)
    e = pd.Timestamp(end_date)
    df = df[(df["净值日期"] >= s) & (df["净值日期"] <= e)].reset_index(drop=True)
    
    if len(df) == 0:
        print(f"❌ {fund_code}: 在 {start_date}~{end_date} 范围内无数据")
        return None
    
    invested = 0
    shares = 0.0
    trades = []
    
    for i in range(len(df)):
        date = df.iloc[i]["净值日期"]
        nav = df.iloc[i]["单位净值"]
        if i == 0:
            s = weekly_amount / nav
            shares += s
            invested += weekly_amount
            trades.append({"date": date, "nav": nav, "inv": invested, "val": shares * nav})
        else:
            prev = df.iloc[i-1]["净值日期"]
            if (date - prev).days >= 4:
                s = weekly_amount / nav
                shares += s
                invested += weekly_amount
                trades.append({"date": date, "nav": nav, "inv": invested, "val": shares * nav})
    
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
        "nav_first": df["单位净值"].iloc[0],
        "nav_last": df["单位净值"].iloc[-1],
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        code = sys.argv[1]
        name = sys.argv[2] if len(sys.argv) > 2 else code
        amount = float(sys.argv[3]) if len(sys.argv) > 3 else 500
    else:
        code = "005561"
        name = "中证红利低波(005561)"
        amount = 500
    
    print(f"\n⏳ 获取 {name} 数据...")
    r = weekly_dca_backtest(code, name, amount)
    
    if r:
        print("=" * 60)
        print(f"📊 {r['fund']} 周定投回测")
        print("=" * 60)
        print(f"  周期:  {r['start'].date()} ~ {r['end'].date()} ({r['years']}年)")
        print(f"  每周:  ¥{amount:,.0f}")
        print("-" * 60)
        print(f"  总投入: ¥{r['invested']:>8,.2f}")
        print(f"  最终值: ¥{r['final_value']:>8,.2f}")
        print(f"  总收益: ¥{r['final_value'] - r['invested']:>8,.2f}")
        print(f"  收益率: {r['total_return']:>+8.2%}")
        print(f"  年化:   {r['annual_return']:>+8.2%}")
        print(f"  定投:   {r['trade_count']} 次")
        print("=" * 60)
        
        # 年度
        df_t = pd.DataFrame(r['trades'])
        print(f"\n📅 年度:")
        for y in range(r['start'].year, r['end'].year + 1):
            yr = df_t[df_t["date"].dt.year <= y]
            if not yr.empty:
                last = yr.iloc[-1]
                ret = (last["val"] - last["inv"]) / last["inv"]
                print(f"  {y}: ¥{last['inv']:<7,.0f} → ¥{last['val']:<9,.2f} ({ret:>+.2%})")
