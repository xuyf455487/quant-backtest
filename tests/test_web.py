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
from web.app import (
    _PAGE_HTML,
    build_chart,
    build_compare_payload,
    build_hot_stocks_payload,
    build_stock_lookup_payload,
    normalize_a_share_symbol,
    prepare_backtest_dataset,
)


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


def test_normalize_a_share_symbol_adds_market_prefix():
    """测试A股代码自动补全市场前缀"""
    assert normalize_a_share_symbol("600519") == "sh600519"
    assert normalize_a_share_symbol("000001") == "sz000001"
    assert normalize_a_share_symbol("300750") == "sz300750"
    assert normalize_a_share_symbol("sh600036") == "sh600036"
    print("✅ test_normalize_a_share_symbol_adds_market_prefix PASS")


def test_hot_stocks_payload_falls_back_when_fetcher_fails():
    """测试热门股接口失败时返回内置备用列表"""
    def failing_fetcher():
        raise RuntimeError("network unavailable")

    payload = build_hot_stocks_payload(fetcher=failing_fetcher, limit=3)

    assert payload["source"] == "fallback"
    assert len(payload["items"]) == 3
    assert payload["items"][0]["symbol"].startswith(("sh", "sz", "bj"))
    assert {"symbol", "code", "name", "latest", "change_pct", "turnover"} <= set(payload["items"][0])
    print("✅ test_hot_stocks_payload_falls_back_when_fetcher_fails PASS")


def test_stock_lookup_uses_fallback_name_for_known_symbol():
    """测试股票名称识别可从备用热门池匹配常见代码"""
    payload = build_stock_lookup_payload(
        "600519",
        hot_stock_fetcher=lambda: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    assert payload["symbol"] == "sh600519"
    assert payload["code"] == "600519"
    assert payload["name"] == "贵州茅台"
    assert payload["source"] == "fallback"
    print("✅ test_stock_lookup_uses_fallback_name_for_known_symbol PASS")


def test_stock_lookup_uses_fallback_when_realtime_misses_known_symbol():
    """测试实时榜单未命中时继续使用内置热门池识别常见股票"""
    import pandas as pd

    realtime = pd.DataFrame([{
        "代码": "000001",
        "名称": "平安银行",
        "最新价": 10.0,
        "涨跌幅": 0.5,
        "成交额": 1000000.0,
    }])

    payload = build_stock_lookup_payload("600519", hot_stock_fetcher=lambda: realtime)

    assert payload["symbol"] == "sh600519"
    assert payload["name"] == "贵州茅台"
    assert payload["source"] == "fallback"
    print("✅ test_stock_lookup_uses_fallback_when_realtime_misses_known_symbol PASS")


def test_prepare_backtest_dataset_uses_historical_first_close_for_auto_price():
    """测试自动起始价使用历史行情首日收盘价"""
    data = generate_stock_data("sh600519", days=120, start_price=180, seed=21)

    def fake_fetcher(symbol, days):
        assert symbol == "sh600519"
        assert days == 120
        return data

    prepared, meta = prepare_backtest_dataset(
        symbol="600519",
        days=120,
        start_price=None,
        auto_price=True,
        use_real_data=True,
        hist_fetcher=fake_fetcher,
    )

    assert len(prepared) == 120
    assert meta["symbol"] == "sh600519"
    assert meta["data_source"] == "historical"
    assert meta["price_source"] == "historical_first_close"
    assert meta["start_price"] == round(float(data["close"].iloc[0]), 2)
    print("✅ test_prepare_backtest_dataset_uses_historical_first_close_for_auto_price PASS")


def test_backtest_dataset_manual_override_uses_simulation_price():
    """测试手动覆盖起始价时使用模拟数据指定价格"""
    data, meta = prepare_backtest_dataset(
        symbol="300750",
        days=100,
        start_price=188.5,
        auto_price=False,
        use_real_data=False,
        seed=7,
    )

    assert meta["symbol"] == "sz300750"
    assert meta["data_source"] == "simulated_fallback"
    assert meta["price_source"] == "manual_override"
    assert meta["start_price"] == 188.5
    assert len(data) == 100
    print("✅ test_backtest_dataset_manual_override_uses_simulation_price PASS")


def test_page_html_includes_stock_discovery_controls():
    """测试页面包含热门股、股票身份和高级起始价控件"""
    assert 'id="hotStocks"' in _PAGE_HTML
    assert 'id="symbolIdentity"' in _PAGE_HTML
    assert 'id="priceSource"' in _PAGE_HTML
    assert 'id="advancedSettings"' in _PAGE_HTML
    assert 'id="manualPriceToggle"' in _PAGE_HTML
    assert "loadHotStocks" in _PAGE_HTML
    assert "lookupSymbol" in _PAGE_HTML
    print("✅ test_page_html_includes_stock_discovery_controls PASS")


def run_tests():
    tests = [
        test_build_compare_payload_returns_metrics_curves_and_chart,
        test_build_chart_returns_plotly_json_without_inline_scripts,
        test_page_html_uses_research_workbench_layout,
        test_normalize_a_share_symbol_adds_market_prefix,
        test_hot_stocks_payload_falls_back_when_fetcher_fails,
        test_stock_lookup_uses_fallback_name_for_known_symbol,
        test_stock_lookup_uses_fallback_when_realtime_misses_known_symbol,
        test_prepare_backtest_dataset_uses_historical_first_close_for_auto_price,
        test_backtest_dataset_manual_override_uses_simulation_price,
        test_page_html_includes_stock_discovery_controls,
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
