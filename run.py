"""
主入口 — CLI 快速回测（V2 引擎）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scripts.fetch_data import get_stock_data
from strategies.ma_cross import MovingAverageCrossStrategy
from strategies.rsi import RSIStrategy
from strategies.macd import MACDStrategy
from strategies.bollinger import BollingerBandsStrategy
from backtest.engine import run_backtest


STRATEGIES = {
    "1": ("双均线交叉", MovingAverageCrossStrategy),
    "2": ("RSI超买超卖", RSIStrategy),
    "3": ("MACD金叉死叉", MACDStrategy),
    "4": ("布林带突破", BollingerBandsStrategy),
}


def main():
    print("=" * 60)
    print("📈 量化回测系统 v0.2")
    print("=" * 60)

    # 1. 选择策略
    print("\n📋 可选策略:")
    for k, (name, _) in STRATEGIES.items():
        print(f"  [{k}] {name}")

    choice = input("\n选择策略 (默认 1): ").strip() or "1"
    if choice not in STRATEGIES:
        print(f"❌ 无效选择: {choice}")
        return 1

    strategy_name, strategy_cls = STRATEGIES[choice]
    print(f"✅ 已选择: {strategy_name}")

    # 2. 输入参数
    symbol = input("\n股票代码 (默认 sh600519): ").strip() or "sh600519"
    start = input("开始日期 (默认 2020-01-01): ").strip() or "2020-01-01"
    end = input("结束日期 (默认 2025-06-20): ").strip() or "2025-06-20"
    cash = float(input("初始资金 (默认 100000): ").strip() or "100000")

    print(f"\n⏳ 获取 {symbol} 行情数据 ({start} ~ {end})...")

    try:
        data = get_stock_data(symbol, start, end)
        print(f"✅ 获取到 {len(data)} 条数据")

        # 3. 创建策略
        strategy = strategy_cls()
        print(f"📋 策略: {strategy.name}")

        # 4. 运行回测（V2引擎）
        print("⏳ 运行回测...")
        result = run_backtest(data, strategy, initial_capital=cash)

        # 5. 输出结果
        print("\n" + "=" * 60)
        print("📊 回测结果")
        print("=" * 60)
        summary = result.summary()
        for key, value in summary.items():
            print(f"  {key:<16} {value}")

        # 6. 交易明细
        if result.trade_log:
            print(f"\n📝 交易明细 ({len(result.trade_log)} 笔):")
            for t in result.trade_log[:20]:  # 最多显示20笔
                direction = "🟢 买入" if t.direction == "buy" else "🔴 卖出"
                print(f"  {t.date.date()} {direction} {t.shares}股 @ ¥{t.price:.2f}")

        if len(result.trade_log) > 20:
            print(f"  ... 还有 {len(result.trade_log) - 20} 笔未显示")

        print("\n" + "=" * 60)
        print("💡 启动可视化: uvicorn web.app:app --reload")
        print("💡 运行测试: python3 tests/test_engine.py")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
