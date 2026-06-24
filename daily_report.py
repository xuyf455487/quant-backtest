#!/usr/bin/env python3
"""
📈 投资理财助手 — 每日策略推送脚本

功能：
1. 读取 watchlist.yaml 关注列表
2. 获取每只标的当日行情
3. 计算布林带、RSI、MACD 信号 + 综合建议
4. 检查止盈止损价格提醒
5. 生成定投计划建议
6. 输出报告（stdout → cron 捕获推送）

用法：
  source .venv/bin/activate && python daily_report.py [--weekly] [--monthly]

模式：
  (无参数)    → 每日盘中/收盘策略
  --weekly    → 周度总结报告
  --monthly   → 月度总结报告
"""

import sys
import yaml
from pathlib import Path
from datetime import datetime

# ── 路径 ──
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from portfolio.data import fetch_hist
from portfolio.analysis import analyze_asset
from portfolio.alerts import load_alerts, check_alerts, format_alerts_block
from portfolio.report import generate_weekly_report, generate_monthly_report

WATCHLIST_PATH = BASE_DIR / "portfolio" / "watchlist.yaml"


# ── 基础工具 ──
def load_watchlist() -> dict:
    if not WATCHLIST_PATH.exists():
        print(f"❌ 未找到关注列表: {WATCHLIST_PATH}")
        sys.exit(1)
    with open(WATCHLIST_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _safe_asset_row(a):
    """格式化标的单行（Telegram 友好）"""
    name = str(a.get("name", ""))
    close = a.get("close")
    chg = a.get("change")
    adv = a.get("advice", "N/A")
    if a.get("error"):
        return f"⚠️ {name}：{a['error']}"
    close_str = f"¥{close:.2f}" if close is not None else "N/A"
    chg_str = f"{chg:+.2f}%" if chg is not None else "N/A"
    return f"{name}　{close_str}　{chg_str}　{adv}"


# ── 定投建议 ──
def generate_dca_advice(assets: list, dca_config: dict) -> str:
    monthly = dca_config.get("monthly_amount", 5000)
    daily_amount = round(monthly / 22, 2)
    boll_mult = dca_config.get("bollinger_multiplier", 1.5)
    rsi_mult = dca_config.get("rsi_multiplier", 1.3)

    buy_signals = [a for a in assets if a.get("advice") and "加仓" in a["advice"]]
    sell_signals = [a for a in assets if a.get("advice") and "减仓" in a["advice"]]

    lines = ["📊 *定投计划*",
             f"　月定投 ¥{monthly:,.0f}　日均 ¥{daily_amount:.0f}"]

    if buy_signals:
        lines.append("🟢 *加仓信号*（执行日定投 + 酌情加码）：")
        for a in buy_signals:
            is_boll = "买入" in a["bollinger"]["signal"] or "加仓" in a["bollinger"]["signal"]
            is_rsi = "买入" in a["rsi"]["signal"] or "加仓" in a["rsi"]["signal"]
            mult = max(boll_mult, rsi_mult) if is_boll and is_rsi else (boll_mult if is_boll else (rsi_mult if is_rsi else 1.0))
            dca_today = round(daily_amount * mult, 0)
            reasons = []
            if is_boll:
                reasons.append(f"布林({a['bollinger']['detail']})")
            if is_rsi:
                reasons.append(f"RSI({a['rsi']['detail']})")
            lines.append(f"　• {a['name']}　¥{a['close']:.2f}")
            lines.append(f"　　{', '.join(reasons)} → 定投 ¥{dca_today:,.0f}（{mult:.1f}x）")

    if sell_signals:
        lines.append("🔴 *减仓信号*（回调风险）：")
        for a in sell_signals:
            lines.append(f"　• {a['name']}　¥{a['close']:.2f}")

    if not buy_signals and not sell_signals:
        lines.append(f"　➡️ 正常日定投 ¥{daily_amount:.0f}，无特殊信号")

    return "\n".join(lines)


# ── 每日报告 ──
def format_daily_report(assets: list, dca_advice: str, triggered_alerts: list) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []

    # ── 标题 ──
    # 找到数据最新日期
    data_dates = [a.get("data_date") for a in assets if a.get("data_date")]
    max_date = max(data_dates) if data_dates else now.split(" ")[0]
    lines.append(f"📈 *每日投资策略报告*")
    lines.append(f"📅 {now}　📌 数据截至 {max_date}")
    lines.append("")

    # ── 价格提醒 ──
    alert_block = format_alerts_block(triggered_alerts)
    if alert_block:
        lines.append(alert_block.strip())
        lines.append("")

    # ── 个股汇总 ──
    stocks = [a for a in assets if a.get("symbol", "").startswith(("sh", "sz", "bj"))]
    if stocks:
        lines.append("📊 *个股*")
        for a in stocks:
            lines.append(_safe_asset_row(a))
        lines.append("")

    # ── 基金/ETF 汇总 ──
    funds = [a for a in assets if not a.get("symbol", "").startswith(("sh", "sz", "bj"))]
    if funds:
        lines.append("📊 *基金 / ETF*")
        for a in funds:
            lines.append(_safe_asset_row(a))
        lines.append("")

    # ── 详细信号 —— 只显示有买/卖信号的 ──
    signal_items = [a for a in assets if not a.get("error") and a.get("advice") and a["advice"] not in ("N/A", "➡️ 继续持有", "继续持有")]
    if signal_items:
        lines.append("🔍 *信号明细*")
        for a in signal_items:
            price_str = f"¥{a['close']:.2f}" if a['close'] is not None else "N/A"
            chg_str = f"{a['change']:+.2f}%" if a['change'] is not None else "N/A"
            lines.append(f"")
            lines.append(f"*{a['name']}*　{price_str}　{chg_str}")
            lines.append(f"　布林带：{a['bollinger']['signal']}（{a['bollinger']['detail']}）")
            lines.append(f"　RSI：{a['rsi']['signal']}（{a['rsi']['detail']}）")
            lines.append(f"　MACD：{a['macd']['signal']}（{a['macd']['detail']}）")
        lines.append("")

    # ── 定投 ──
    lines.append("━" * 20)
    lines.append(dca_advice)
    lines.append("━" * 20)

    return "\n".join(lines)


# ── 主入口 ──
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--weekly", action="store_true", help="周报模式")
    parser.add_argument("--monthly", action="store_true", help="月报模式")
    args = parser.parse_args()

    print("🚀 投资理财助手 — 策略生成中...\n", file=sys.stderr)

    watchlist = load_watchlist()

    # 周报/月报模式
    if args.weekly:
        print(generate_weekly_report(watchlist))
        return
    if args.monthly:
        print(generate_monthly_report(watchlist))
        return

    # ── 每日模式 ──
    dca_config = watchlist.get("dca", {})

    # 合并标的
    all_items = []
    for item in watchlist.get("stocks", []):
        item["code"] = str(item["code"])
        all_items.append(item)
    for item in watchlist.get("funds", []):
        item["code"] = str(item["code"])
        all_items.append(item)

    if not all_items:
        print("⚠️ 关注列表为空")
        sys.exit(1)

    results = []
    for item in all_items:
        symbol = item["code"]
        name = item.get("name", symbol)
        try:
            df = fetch_hist(symbol, days=100)
            res = analyze_asset(symbol, name, "stock" if symbol.startswith(("sh","sz","bj")) else "fund", df)
        except Exception as e:
            res = {
                "symbol": symbol, "name": name, "error": str(e),
                "close": None, "change": None,
                "bollinger": {"signal": "⚠️ 数据错误", "detail": str(e)},
                "rsi": {"signal": "⚠️ 数据错误", "detail": str(e)},
                "macd": {"signal": "⚠️ 数据错误", "detail": str(e)},
            }
        results.append(res)

    # 检查价格提醒
    triggered = check_alerts(results)

    dca_advice = generate_dca_advice(results, dca_config)
    report = format_daily_report(results, dca_advice, triggered)
    print(report)


if __name__ == "__main__":
    main()
