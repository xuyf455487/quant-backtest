"""
Web 层纯函数测试
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.sim_data import generate_stock_data
from web.app import build_compare_payload


def test_build_compare_payload_returns_metrics_curves_and_chart():
    """测试多策略对比返回指标、净值曲线和图表 HTML"""
    data = generate_stock_data(days=120, seed=11)

    payload = build_compare_payload(["ma_cross", "rsi"], data, initial_capital=100000)

    assert len(payload["results"]) == 2
    assert "<div" in payload["chart"]
    for result in payload["results"]:
        assert result["id"] in ("ma_cross", "rsi")
        assert "metrics" in result
        assert "equity_curve" in result
        assert len(result["equity_curve"]) == len(data)
        assert {"date", "value"} <= set(result["equity_curve"][0].keys())
    print("✅ test_build_compare_payload_returns_metrics_curves_and_chart PASS")


def run_tests():
    tests = [
        test_build_compare_payload_returns_metrics_curves_and_chart,
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
