"""
📅 周报 / 月报生成模块
"""

from datetime import datetime, timedelta
import pandas as pd
from portfolio.data import fetch_hist
from portfolio.analysis import analyze_asset


def generate_weekly_report(watchlist: dict) -> str:
    """生成周度总结报告"""
    return _generate_period_report(watchlist, "周报", days=5)


def generate_monthly_report(watchlist: dict) -> str:
    """生成月度总结报告"""
    return _generate_period_report(watchlist, "月报", days=22)


def _generate_period_report(watchlist: dict, label: str, days: int) -> str:
    now = datetime.now()
    lines = []
    lines.append(f"📊 投资 {label}")
    lines.append(f"   生成时间: {now.strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"   {'='*45}")
    lines.append(f"   统计周期: 最近 {days} 个交易日")

    # 收集所有标的
    all_items = []
    for item in watchlist.get("stocks", []):
        all_items.append(("stock", item))
    for item in watchlist.get("funds", []):
        all_items.append(("fund", item))

    period_perf = []  # [(name, symbol, start_price, end_price, return_pct)]
    best = None
    worst = None

    for atype, item in all_items:
        symbol = str(item["code"])
        name = item.get("name", symbol)

        try:
            df = fetch_hist(symbol, days=days + 10)
            if len(df) < days + 1:
                period_perf.append({"name": name, "error": "数据不足"})
                continue

            start_price = df["close"].iloc[-days - 1]
            end_price = df["close"].iloc[-1]
            ret = (end_price - start_price) / start_price * 100

            entry = {"name": name, "symbol": symbol,
                     "start_price": round(float(start_price), 2),
                     "end_price": round(float(end_price), 2),
                     "return_pct": round(ret, 2)}

            period_perf.append(entry)

            if best is None or ret > best["return_pct"]:
                best = entry
            if worst is None or ret < worst["return_pct"]:
                worst = entry

        except Exception as e:
            period_perf.append({"name": name, "error": str(e)})

    # 输出表现
    lines.append(f"\n📈 期间表现")
    lines.append(f"   {'名称':<16} {'起始价':<10} {'结束价':<10} {'收益率':<10}")
    lines.append(f"   {'─'*50}")
    for p in period_perf:
        if "error" in p:
            lines.append(f"   {p['name']:<16} {'⚠️ '+p['error']:<30}")
        else:
            icon = "🟢" if p["return_pct"] > 0 else "🔴" if p["return_pct"] < 0 else "⚪"
            lines.append(f"   {p['name']:<16} ¥{p['start_price']:<7.2f} ¥{p['end_price']:<7.2f} {icon} {p['return_pct']:+.2f}%")

    # 最佳/最差
    if best and worst:
        lines.append(f"\n🏆 最佳: {best['name']} ({best['return_pct']:+.2f}%)")
        lines.append(f"📉 最差: {worst['name']} ({worst['return_pct']:+.2f}%)")

        total_ret = sum(p.get("return_pct", 0) for p in period_perf if "return_pct" in p)
        avg_ret = total_ret / len([p for p in period_perf if "return_pct" in p])
        lines.append(f"📊 组合平均: {avg_ret:+.2f}%")

    # 信号回顾
    lines.append(f"\n🔍 当前信号速览")
    for atype, item in all_items:
        symbol = str(item["code"])
        name = item.get("name", symbol)
        try:
            df = fetch_hist(symbol, days=100)
            res = analyze_asset(symbol, name, atype, df)
            if res.get("error"):
                lines.append(f"   {name:<14} ⚠️ 数据错误")
            else:
                close = res["close"]
                chg = res["change"]
                lines.append(f"   {name:<14} ¥{close:<7.2f} {chg:+.2f}%  → {res['advice']}")
        except Exception:
            lines.append(f"   {name:<14} ⚠️ 获取失败")

    lines.append(f"\n{'='*45}")
    lines.append(f"💡 编辑 portfolio/watchlist.yaml 调整关注列表")

    return "\n".join(lines)
