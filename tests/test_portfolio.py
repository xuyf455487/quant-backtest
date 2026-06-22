"""
投资监控模块单元测试
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from portfolio import alerts
from portfolio.monitor import is_trading_time


def test_is_trading_time_respects_a_share_sessions():
    """测试 A 股交易时段判断"""
    assert is_trading_time(datetime(2024, 1, 2, 9, 30))
    assert is_trading_time(datetime(2024, 1, 2, 11, 29))
    assert not is_trading_time(datetime(2024, 1, 2, 11, 30))
    assert not is_trading_time(datetime(2024, 1, 2, 12, 30))
    assert is_trading_time(datetime(2024, 1, 2, 13, 0))
    assert is_trading_time(datetime(2024, 1, 2, 14, 59))
    assert not is_trading_time(datetime(2024, 1, 2, 15, 0))
    assert not is_trading_time(datetime(2024, 1, 6, 10, 0))
    print("✅ test_is_trading_time_respects_a_share_sessions PASS")


def test_check_alerts_triggers_with_current_prices():
    """测试价格提醒在传入当前价格时可以触发"""
    original_load_alerts = alerts.load_alerts
    try:
        alerts.load_alerts = lambda: [
            {"symbol": "sh600519", "name": "贵州茅台", "direction": "跌破", "price": 1500.0},
            {"symbol": "159915", "name": "创业板ETF", "direction": "涨破", "price": 2.0},
        ]
        triggered = alerts.check_alerts([
            {"symbol": "sh600519", "close": 1499.0},
            {"symbol": "159915", "close": 2.1},
        ])
    finally:
        alerts.load_alerts = original_load_alerts

    assert len(triggered) == 2
    assert {item["symbol"] for item in triggered} == {"sh600519", "159915"}
    print("✅ test_check_alerts_triggers_with_current_prices PASS")


def run_tests():
    tests = [
        test_is_trading_time_respects_a_share_sessions,
        test_check_alerts_triggers_with_current_prices,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} FAIL: {e}")
            failed += 1
    return passed, failed


if __name__ == "__main__":
    passed, failed = run_tests()
    print(f"结果: {passed} 通过, {failed} 失败 / {passed + failed} 总")
    sys.exit(1 if failed else 0)
