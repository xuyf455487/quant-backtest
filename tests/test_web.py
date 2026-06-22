"""
Web 层纯函数测试
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.engine import run_backtest
from scripts.sim_data import generate_stock_data
from strategies.ma_cross import MovingAverageCrossStrategy
from web.app import _PAGE_HTML, build_chart, build_compare_payload


def test_build_compare_payload_returns_metrics_curves_and_chart():
    """测试多策略对比返回指标、净值曲线和可渲染图表 JSON"""
    data = generate_stock_data(days=120, seed=11)

    payload = build_compare_payload(["ma_cross", "rsi"], data, initial_capital=100000)

    assert len(payload["results"]) == 2
    chart = json.loads(payload["chart"])
    assert "data" in chart
    assert "layout" in chart
    assert "<script" not in payload["chart"]
    assert "plotly.js" not in payload["chart"]
    for result in payload["results"]:
        assert result["id"] in ("ma_cross", "rsi")
        assert "metrics" in result
        assert "equity_curve" in result
        assert len(result["equity_curve"]) == len(data)
        assert {"date", "value"} <= set(result["equity_curve"][0].keys())
    print("✅ test_build_compare_payload_returns_metrics_curves_and_chart PASS")


def test_build_chart_returns_plotly_json_without_inline_scripts():
    """测试单策略回测图表返回 Plotly JSON，而不是 innerHTML 无法执行的 script"""
    data = generate_stock_data(days=120, seed=12)
    result = run_backtest(data, MovingAverageCrossStrategy(), initial_capital=100000)

    chart = build_chart(data, result)

    parsed = json.loads(chart)
    assert "data" in parsed
    assert "layout" in parsed
    assert "<script" not in chart
    assert "plotly.js" not in chart
    print("✅ test_build_chart_returns_plotly_json_without_inline_scripts PASS")


def test_page_html_uses_research_workbench_layout():
    """测试页面使用研究工作台布局和右侧洞察栏"""
    assert "Quant Research Workbench" in _PAGE_HTML
    assert 'class="app-shell"' in _PAGE_HTML
    assert 'id="insightsPanel"' in _PAGE_HTML
    assert 'id="analysisGrid"' in _PAGE_HTML
    assert "function renderInsights" in _PAGE_HTML
    assert "Plotly.newPlot" in _PAGE_HTML
    assert "量化回测系统" not in _PAGE_HTML
    print("✅ test_page_html_uses_research_workbench_layout PASS")


def run_tests():
    tests = [
        test_build_compare_payload_returns_metrics_curves_and_chart,
        test_build_chart_returns_plotly_json_without_inline_scripts,
        test_page_html_uses_research_workbench_layout,
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
