"""
🎯 止盈/止损价格阈值提醒
"""

import yaml
import os
from pathlib import Path
from datetime import datetime

ALERTS_PATH = Path(__file__).parent / "alerts.yaml"


def load_alerts() -> list:
    """加载价格提醒配置"""
    if not ALERTS_PATH.exists():
        return []
    with open(ALERTS_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("alerts", [])


def save_alert(alert: dict):
    """添加一条价格提醒"""
    alerts = load_alerts()
    # 去重
    for a in alerts:
        if (a["symbol"] == alert["symbol"] and
            a["direction"] == alert["direction"] and
            abs(a["price"] - alert["price"]) < 0.001):
            print(f"⚠️ 已存在相同提醒: {alert['name']} {alert['direction']} ¥{alert['price']}")
            return
    alerts.append(alert)
    _write_alerts(alerts)
    print(f"✅ 已添加提醒: {alert['name']} {alert['direction']} ¥{alert['price']}")


def remove_alert(symbol: str = None, direction: str = None, price: float = None):
    """删除价格提醒"""
    alerts = load_alerts()
    before = len(alerts)
    alerts = [a for a in alerts if not (
        (symbol is None or a["symbol"] == symbol) and
        (direction is None or a["direction"] == direction) and
        (price is None or abs(a["price"] - price) < 0.001)
    )]
    removed = before - len(alerts)
    _write_alerts(alerts)
    print(f"✅ 已删除 {removed} 条提醒")


def _write_alerts(alerts: list):
    """写入提醒配置"""
    with open(ALERTS_PATH, "w", encoding="utf-8") as f:
        yaml.dump({"alerts": alerts}, f, allow_unicode=True, default_flow_style=False)


def check_alerts(asset_results: list) -> list:
    """
    检查所有价格提醒是否触发
    返回触发列表: [{"name", "symbol", "direction", "price", "current_price"}]
    """
    alerts = load_alerts()
    if not alerts:
        return []

    price_map = {r["symbol"]: r.get("close") for r in asset_results}
    triggered = []

    for a in alerts:
        current = price_map.get(a["symbol"])
        if current is None:
            continue
        if a["direction"] == "跌破" and current <= a["price"]:
            triggered.append({**a, "current_price": current, "triggered_at": datetime.now().strftime("%Y-%m-%d %H:%M")})
        elif a["direction"] == "涨破" and current >= a["price"]:
            triggered.append({**a, "current_price": current, "triggered_at": datetime.now().strftime("%Y-%m-%d %H:%M")})

    return triggered


def format_alerts_block(triggered: list) -> str:
    """格式化触发提醒文本"""
    if not triggered:
        return ""
    lines = ["🔔 价格提醒触发："]
    for t in triggered:
        direction_icon = "📉" if t["direction"] == "跌破" else "📈"
        lines.append(f"   {direction_icon} {t['name']} ({t['symbol']})")
        lines.append(f"     目标: {t['direction']} ¥{t['price']:.2f}")
        lines.append(f"     当前: ¥{t['current_price']:.2f}")
        lines.append(f"     时间: {t['triggered_at']}")
    return "\n".join(lines) + "\n"


# ── CLI 管理 ──
def main():
    import argparse
    parser = argparse.ArgumentParser(description="管理价格提醒")
    parser.add_argument("action", choices=["add", "remove", "list"], help="操作")
    parser.add_argument("--symbol", help="标的代码")
    parser.add_argument("--name", help="标的名称")
    parser.add_argument("--direction", choices=["跌破", "涨破"], help="方向")
    parser.add_argument("--price", type=float, help="触发价格")

    args = parser.parse_args()

    if args.action == "list":
        alerts = load_alerts()
        if not alerts:
            print("📭 无价格提醒")
        else:
            print(f"📋 当前价格提醒 ({len(alerts)} 条):")
            for i, a in enumerate(alerts, 1):
                print(f"  {i}. {a.get('name','?'):<12} {a['symbol']:<12} {a['direction']} ¥{a['price']:.2f}")
        return

    if args.action == "add":
        if not all([args.symbol, args.name, args.direction, args.price is not None]):
            parser.error("add 需要 --symbol --name --direction --price")
        save_alert({
            "symbol": args.symbol,
            "name": args.name,
            "direction": args.direction,
            "price": args.price,
        })
        return

    if args.action == "remove":
        remove_alert(
            symbol=args.symbol,
            direction=args.direction,
            price=args.price,
        )


if __name__ == "__main__":
    main()
