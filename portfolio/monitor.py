#!/usr/bin/env python3
"""
⚡ 盘中异动监控脚本

每10分钟运行一次，检查：
1. 单日跌幅 > 3% → 推送提醒
2. RSI 进入极端区 (< 25) → 推送提醒
3. 价格提醒触发

用法（cron 每10分钟）：
  cd /home/yunfeixu/quant-backtest && .venv/bin/python portfolio/monitor.py

只在交易时段（9:30-15:00）工作日执行有意义。
仅在检测到异动时才有 stdout 输出（静默=正常）。
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from datetime import datetime

from portfolio.data import fetch_hist
from portfolio.analysis import analyze_asset, calc_rsi, calc_change
from portfolio.alerts import check_alerts, format_alerts_block

WATCHLIST_PATH = Path(__file__).parent / "watchlist.yaml"
ALERT_THRESHOLD = -3.0   # 单日跌超3%提醒


def is_trading_time(now: datetime) -> bool:
    """判断当前时间是否处于 A 股连续竞价时段。"""
    if now.weekday() >= 5:
        return False

    hour = now.hour
    minute = now.minute
    in_morning = (hour == 9 and minute >= 30) or hour == 10 or (hour == 11 and minute < 30)
    in_afternoon = hour == 13 or hour == 14
    return in_morning or in_afternoon


def load_watchlist() -> list:
    with open(WATCHLIST_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    items = []
    for item in data.get("stocks", []):
        items.append(item)
    for item in data.get("funds", []):
        items.append(item)
    return items


def main():
    now = datetime.now()
    # 非交易时段直接静默退出
    if not is_trading_time(now):
        return

    items = load_watchlist()
    alerts = []
    asset_results = []

    for item in items:
        symbol = str(item["code"])
        name = item.get("name", symbol)
        try:
            df = fetch_hist(symbol, days=30)
            if df.empty or len(df) < 2:
                continue
        except Exception:
            continue

        change = calc_change(df)
        close = df["close"].iloc[-1]
        asset_results.append({"symbol": symbol, "name": name, "close": close})

        # 1. 单日暴跌
        if change <= ALERT_THRESHOLD:
            alerts.append(f"🔴 异动: {name} ({symbol}) 今日暴跌 {change:.1f}%，现价 ¥{close:.2f}")

        # 2. RSI 极端
        rsi_res = calc_rsi(df)
        if "RSI=" in rsi_res.get("detail", ""):
            import re
            m = re.search(r"RSI=(\d+\.?\d*)", rsi_res["detail"])
            if m and float(m.group(1)) < 25:
                alerts.append(f"🟣 极度超卖: {name} ({symbol}) RSI={float(m.group(1)):.1f}，现价 ¥{close:.2f}")

        # 3. 单日猛涨 (>5%)
        if change >= 5.0:
            alerts.append(f"🟢 异动: {name} ({symbol}) 今日猛涨 {change:.1f}%，现价 ¥{close:.2f}")

    # 价格提醒
    price_alerts = check_alerts(asset_results)

    if not alerts and not price_alerts:
        return  # 静默退出，无输出

    print(f"⚡ 盘中异动监控 ({now.strftime('%H:%M')})")
    print(f"   {'='*35}")

    for a in alerts:
        print(f"\n  {a}")

    if price_alerts:
        print(f"\n  {format_alerts_block(price_alerts)}")

    print(f"\n💡 完整策略见 11:20 / 14:50 推送")


if __name__ == "__main__":
    main()
