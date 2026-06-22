"""
Web 可视化服务 — FastAPI + Plotly 交互图表

启动: uvicorn web.app:app --reload
访问: http://localhost:8000
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
from datetime import datetime
from typing import Callable, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.sim_data import generate_stock_data, STRATEGY_DESCRIPTIONS, get_demo_result
from backtest.engine import run_backtest
from portfolio.data import fetch_hist
from strategies.ma_cross import MovingAverageCrossStrategy
from strategies.rsi import RSIStrategy
from strategies.macd import MACDStrategy
from strategies.bollinger import BollingerBandsStrategy

# App 配置
pio.templates.default = "plotly_white"

app = FastAPI(
    title="量化回测系统",
    description="股票/基金回测可视化工具",
    version="0.2.0",
)

STRATEGY_MAP = {
    "ma_cross": MovingAverageCrossStrategy,
    "rsi": RSIStrategy,
    "macd": MACDStrategy,
    "bollinger": BollingerBandsStrategy,
}

FALLBACK_HOT_STOCKS = [
    {"symbol": "sh600519", "code": "600519", "name": "贵州茅台", "latest": 1500.0, "change_pct": 0.0, "turnover": 0.0},
    {"symbol": "sz300750", "code": "300750", "name": "宁德时代", "latest": 200.0, "change_pct": 0.0, "turnover": 0.0},
    {"symbol": "sh600036", "code": "600036", "name": "招商银行", "latest": 35.0, "change_pct": 0.0, "turnover": 0.0},
    {"symbol": "sz002594", "code": "002594", "name": "比亚迪", "latest": 250.0, "change_pct": 0.0, "turnover": 0.0},
    {"symbol": "sh600030", "code": "600030", "name": "中信证券", "latest": 20.0, "change_pct": 0.0, "turnover": 0.0},
    {"symbol": "sh601012", "code": "601012", "name": "隆基绿能", "latest": 18.0, "change_pct": 0.0, "turnover": 0.0},
    {"symbol": "sz300059", "code": "300059", "name": "东方财富", "latest": 12.0, "change_pct": 0.0, "turnover": 0.0},
    {"symbol": "sh601318", "code": "601318", "name": "中国平安", "latest": 45.0, "change_pct": 0.0, "turnover": 0.0},
    {"symbol": "sz000002", "code": "000002", "name": "万科A", "latest": 8.0, "change_pct": 0.0, "turnover": 0.0},
    {"symbol": "sh510300", "code": "510300", "name": "沪深300ETF", "latest": 4.0, "change_pct": 0.0, "turnover": 0.0},
]


def _chart_json(fig: go.Figure) -> str:
    """Serialize Plotly figures as data so the browser can render them explicitly."""
    return pio.to_json(fig, validate=False)


def normalize_a_share_symbol(symbol: str) -> str:
    """Normalize common A-share inputs to exchange-prefixed symbols."""
    raw = (symbol or "").strip().lower()
    if raw.startswith(("sh", "sz", "bj")):
        return raw
    code = "".join(ch for ch in raw if ch.isdigit())
    if code.startswith(("6", "5")):
        return f"sh{code}"
    if code.startswith(("0", "2", "3")):
        return f"sz{code}"
    if code.startswith(("4", "8")):
        return f"bj{code}"
    return raw


def _symbol_parts(symbol: str) -> tuple[str, str]:
    normalized = normalize_a_share_symbol(symbol)
    code = normalized[2:] if normalized[:2] in ("sh", "sz", "bj") else normalized
    return normalized, code


def _fallback_hot_stocks(limit: int = 10) -> list[dict]:
    return FALLBACK_HOT_STOCKS[:limit]


def build_hot_stocks_payload(fetcher: Optional[Callable[[], pd.DataFrame]] = None, limit: int = 10) -> dict:
    """Build A-share hot stock payload from realtime turnover rank with fallback."""
    if fetcher is None:
        import akshare as ak
        fetcher = ak.stock_zh_a_spot_em

    try:
        df = fetcher()
        if df is None or df.empty:
            raise ValueError("empty realtime hot stock data")
        df = df.sort_values("成交额", ascending=False).head(limit)
        items = []
        for _, row in df.iterrows():
            code = str(row["代码"]).zfill(6)
            symbol = normalize_a_share_symbol(code)
            items.append({
                "symbol": symbol,
                "code": code,
                "name": str(row.get("名称", "")),
                "latest": round(float(row.get("最新价", 0) or 0), 2),
                "change_pct": round(float(row.get("涨跌幅", 0) or 0), 2),
                "turnover": round(float(row.get("成交额", 0) or 0), 2),
            })
        return {"source": "realtime", "items": items}
    except Exception:
        return {"source": "fallback", "items": _fallback_hot_stocks(limit)}


def build_stock_lookup_payload(
    symbol: str,
    hot_stock_fetcher: Optional[Callable[[], pd.DataFrame]] = None,
) -> dict:
    """Resolve a stock code to normalized symbol and best-effort name."""
    normalized, code = _symbol_parts(symbol)
    hot_payload = build_hot_stocks_payload(fetcher=hot_stock_fetcher, limit=80)
    for item in hot_payload["items"]:
        if item["symbol"] == normalized or item["code"] == code:
            return {
                "symbol": item["symbol"],
                "code": item["code"],
                "name": item["name"],
                "latest": item["latest"],
                "source": hot_payload["source"],
            }
    for item in FALLBACK_HOT_STOCKS:
        if item["symbol"] == normalized or item["code"] == code:
            return {
                "symbol": item["symbol"],
                "code": item["code"],
                "name": item["name"],
                "latest": item["latest"],
                "source": "fallback",
            }
    return {"symbol": normalized, "code": code, "name": None, "latest": None, "source": "unknown"}


def prepare_backtest_dataset(
    symbol: str,
    days: int,
    start_price: Optional[float],
    auto_price: bool = True,
    use_real_data: bool = True,
    seed: int = 42,
    hist_fetcher: Callable[[str, int], pd.DataFrame] = fetch_hist,
) -> tuple[pd.DataFrame, dict]:
    """Prepare historical data first, with simulated fallback and price metadata."""
    normalized = normalize_a_share_symbol(symbol)
    if use_real_data:
        try:
            data = hist_fetcher(normalized, days)
            if data is not None and not data.empty:
                first_close = round(float(data["close"].iloc[0]), 2)
                return data, {
                    "symbol": normalized,
                    "data_source": "historical",
                    "price_source": "historical_first_close",
                    "start_price": first_close,
                }
        except Exception:
            pass

    simulated_start = 100.0
    price_source = "simulated_default"
    if not auto_price and start_price is not None:
        simulated_start = float(start_price)
        price_source = "manual_override"
    data = generate_stock_data(symbol=normalized, days=days, start_price=simulated_start, seed=seed)
    return data, {
        "symbol": normalized,
        "data_source": "simulated_fallback",
        "price_source": price_source,
        "start_price": round(float(simulated_start), 2),
    }


def build_compare_payload(strategy_ids: list, data: pd.DataFrame, initial_capital: float = 100000) -> dict:
    """运行多策略对比并返回指标、净值曲线和图表 JSON。"""
    valid_ids = [sid for sid in strategy_ids if sid in STRATEGY_MAP]
    if not valid_ids:
        raise ValueError("没有有效的策略ID")

    results = []
    fig = go.Figure()

    for sid in valid_ids:
        strategy = STRATEGY_MAP[sid]()
        result = run_backtest(data, strategy, initial_capital=initial_capital)
        name = STRATEGY_DESCRIPTIONS[sid]["name"]
        curve = [
            {"date": idx.strftime("%Y-%m-%d"), "value": round(float(value), 2)}
            for idx, value in result.equity_curve.items()
        ]

        results.append({
            "id": sid,
            "name": name,
            "metrics": result.summary(),
            "equity_curve": curve,
            "trade_count": len(result.trade_log),
            "errors": result.errors,
        })

        fig.add_trace(
            go.Scatter(
                x=[p["date"] for p in curve],
                y=[p["value"] for p in curve],
                mode="lines",
                name=name,
            )
        )

    buy_hold = data["close"].values / data["close"].iloc[0] * initial_capital
    fig.add_trace(
        go.Scatter(
            x=data["date"],
            y=buy_hold,
            mode="lines",
            name="买入持有",
            line=dict(color="#888", width=1.5, dash="dash"),
        )
    )
    fig.update_layout(
        template="plotly_white",
        height=520,
        title="策略净值对比",
        hovermode="x unified",
        margin=dict(l=40, r=20, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#ffffff",
        font=dict(color="#111827"),
    )

    return {
        "results": results,
        "chart": _chart_json(fig),
    }


def build_chart(data: pd.DataFrame, result) -> str:
    """
    生成完整的回测图表 JSON

    包含:
    1. K线 + 均线 + 买卖点 + 资产曲线
    2. 成交量
    3. 指标卡片
    """
    # 判断是否有 trade_signal
    df = data.copy()
    if "ma_short" not in df.columns and "trade_signal" not in df.columns:
        from strategies.ma_cross import MovingAverageCrossStrategy
        s = MovingAverageCrossStrategy()
        df = s.generate_signals(df)

    # ===== 主图：K线 + 均线 + 资产曲线 + 买卖点 =====
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.55, 0.20, 0.25],
        subplot_titles=("价格走势与信号", "成交量", "策略收益曲线"),
    )

    # K线
    fig.add_trace(
        go.Candlestick(
            x=df["date"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="K线",
            showlegend=False,
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        ),
        row=1, col=1,
    )

    # 均线
    if "ma_short" in df.columns:
        fig.add_trace(
            go.Scatter(x=df["date"], y=df["ma_short"],
                       mode="lines", name=f"MA{5}",
                       line=dict(color="#FFD700", width=1.5)),
            row=1, col=1,
        )
    if "ma_long" in df.columns:
        fig.add_trace(
            go.Scatter(x=df["date"], y=df["ma_long"],
                       mode="lines", name=f"MA{20}",
                       line=dict(color="#FF6B6B", width=1.5)),
            row=1, col=1,
        )

    # RSI 在第二张图
    if "rsi" in df.columns:
        fig2 = make_subplots(rows=3, cols=1, shared_xaxes=True,
                             vertical_spacing=0.04, row_heights=[0.4, 0.2, 0.2],
                             subplot_titles=("价格走势", "RSI", "成交量"))
        fig = fig2
        fig.add_trace(go.Candlestick(x=df["date"], open=df["open"], high=df["high"],
                                      low=df["low"], close=df["close"], name="K线",
                                      showlegend=False), row=1, col=1)
        fig.add_trace(go.Scatter(x=df["date"], y=df["rsi"], mode="lines",
                                  name="RSI", line=dict(color="#7C4DFF", width=2)),
                      row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

    # 买卖点
    if "trade_signal" in df.columns:
        buy_signals = df[df["trade_signal"] == 1]
        sell_signals = df[df["trade_signal"] == -1]

        if not buy_signals.empty:
            fig.add_trace(
                go.Scatter(x=buy_signals["date"], y=buy_signals["close"],
                           mode="markers",
                           marker=dict(symbol="triangle-up", size=14,
                                       color="#26a69a", line=dict(width=2, color="white")),
                           name="买入信号"),
                row=1, col=1,
            )
        if not sell_signals.empty:
            fig.add_trace(
                go.Scatter(x=sell_signals["date"], y=sell_signals["close"],
                           mode="markers",
                           marker=dict(symbol="triangle-down", size=14,
                                       color="#ef5350", line=dict(width=2, color="white")),
                           name="卖出信号"),
                row=1, col=1,
            )

    # 成交量
    colors = ["#26a69a" if df["close"].iloc[i] >= df["open"].iloc[i] else "#ef5350"
              for i in range(len(df))]
    fig.add_trace(
        go.Bar(x=df["date"], y=df["volume"], name="成交量",
               marker_color=colors, opacity=0.6),
        row=2 if "rsi" in df.columns else 2, col=1,
    )

    # 资产曲线
    if result is not None and result.equity_curve is not None:
        eq = result.equity_curve
        fig.add_trace(
            go.Scatter(x=eq.index, y=eq.values,
                       mode="lines",
                       name="策略资产",
                       line=dict(color="#FFD700", width=2),
                       fill="tozeroy",
                       fillcolor="rgba(255,215,0,0.1)"),
            row=3, col=1,
        )

        # 基准线（等值买入持有）
        if data is not None:
            buy_hold = data["close"].values / data["close"].iloc[0] * result.initial_capital
            fig.add_trace(
                go.Scatter(x=data["date"], y=buy_hold,
                           mode="lines",
                           name="买入持有",
                           line=dict(color="#7C4DFF", width=1.5, dash="dash")),
                row=3, col=1,
            )

    # 布局
    fig.update_layout(
        template="plotly_white",
        height=680,
        dragmode="zoom",
        hovermode="x unified",
        margin=dict(l=40, r=20, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis3_rangeslider_visible=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#ffffff",
        font=dict(color="#111827"),
    )

    fig.update_xaxes(title_text="日期", row=3, col=1)
    fig.update_yaxes(title_text="价格", row=1, col=1)
    fig.update_yaxes(title_text="成交量", row=2, col=1)
    fig.update_yaxes(title_text="资产(¥)", row=3, col=1)

    return _chart_json(fig)


@app.get("/", response_class=HTMLResponse)
async def root():
    """主页"""
    return HTMLResponse(_PAGE_HTML)


@app.get("/api/strategies")
async def list_strategies():
    """获取策略列表"""
    return {
        "strategies": [
            {"id": sid, **info}
            for sid, info in STRATEGY_DESCRIPTIONS.items()
        ]
    }


@app.get("/api/hot-stocks")
async def hot_stocks(limit: int = Query(10, ge=1, le=30)):
    """获取A股成交额热门股，失败时返回内置备用列表"""
    return build_hot_stocks_payload(limit=limit)


@app.get("/api/stock/lookup")
async def stock_lookup(symbol: str = Query(..., description="股票代码")):
    """解析A股股票名称和规范代码"""
    return build_stock_lookup_payload(symbol)


@app.get("/api/backtest")
async def run_backtest_api(
    strategy_id: str = Query("ma_cross", description="策略ID"),
    symbol: str = Query("sh600519", description="股票代码"),
    days: int = Query(500, description="数据天数", ge=100, le=2000),
    start_price: Optional[float] = Query(None, description="手动起始价格", ge=10),
    cash: float = Query(100000, description="初始资金"),
    auto_price: bool = Query(True, description="是否自动使用历史首日价格"),
    use_real_data: bool = Query(True, description="是否优先使用真实历史行情"),
    seed: int = Query(42, description="随机种子"),
):
    """运行回测并返回结果"""
    if strategy_id not in STRATEGY_MAP:
        raise HTTPException(400, f"不支持的策略: {strategy_id}，可选: {list(STRATEGY_MAP.keys())}")

    data, data_meta = prepare_backtest_dataset(
        symbol=symbol,
        days=days,
        start_price=start_price,
        auto_price=auto_price,
        use_real_data=use_real_data,
        seed=seed,
    )

    # 创建策略
    cls = STRATEGY_MAP[strategy_id]
    strategy = cls()

    # 运行回测
    result = run_backtest(data, strategy, initial_capital=cash)

    # 生成图表
    chart_html = build_chart(data, result)

    return {
        "symbol": data_meta["symbol"],
        "data_source": data_meta["data_source"],
        "price_source": data_meta["price_source"],
        "start_price": data_meta["start_price"],
        "metrics": result.summary(),
        "trade_count": len(result.trade_log),
        "errors": result.errors,
        "chart": chart_html,
        "chart_total": len(chart_html),
    }


@app.get("/api/backtest/demo")
async def demo_backtest():
    """快速演示（无需参数）"""
    data, result, name = get_demo_result()
    chart_html = build_chart(data, result)

    return {
        "strategy": name,
        "symbol": "sh600519",
        "data_source": "simulated_demo",
        "price_source": "demo_seed_price",
        "start_price": round(float(data["close"].iloc[0]), 2),
        "metrics": result.summary(),
        "chart": chart_html,
    }


@app.get("/api/compare")
async def compare_strategies(
    strategies: str = Query("ma_cross,rsi,macd,bollinger", description="逗号分隔的策略ID"),
    days: int = Query(500, ge=100),
    seed: int = Query(42),
):
    """多策略对比"""
    ids = [s.strip() for s in strategies.split(",")]
    ids = [s for s in ids if s in STRATEGY_MAP]

    if not ids:
        raise HTTPException(400, "没有有效的策略ID")

    data = generate_stock_data(days=days, seed=seed)
    return build_compare_payload(ids, data)


_PAGE_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Quant Research Workbench</title>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <style>
        :root {
            --bg: #f4f7fb;
            --panel: #ffffff;
            --panel-muted: #f8fafc;
            --line: #dbe3ef;
            --line-soft: #e8edf5;
            --text: #111827;
            --muted: #64748b;
            --muted-2: #94a3b8;
            --blue: #1d4ed8;
            --blue-soft: #dbeafe;
            --green: #0f766e;
            --green-soft: #ccfbf1;
            --red: #dc2626;
            --red-soft: #fee2e2;
            --amber: #b45309;
            --amber-soft: #fef3c7;
            --radius: 10px;
            --shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
        }

        .app-shell { min-height: 100vh; }

        .app-bar {
            min-height: 72px;
            background: var(--panel);
            border-bottom: 1px solid var(--line);
            padding: 14px 28px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 24px;
        }

        .eyebrow {
            color: var(--blue);
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 3px;
        }

        .app-bar h1 {
            font-size: 20px;
            line-height: 1.2;
            font-weight: 750;
            letter-spacing: 0;
        }

        .app-bar p {
            color: var(--muted);
            font-size: 12px;
            margin-top: 4px;
        }

        .system-status {
            display: flex;
            align-items: center;
            gap: 10px;
            color: var(--muted);
            font-size: 12px;
            white-space: nowrap;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 999px;
            background: var(--green);
            box-shadow: 0 0 0 3px var(--green-soft);
        }

        .workbench {
            max-width: 1480px;
            margin: 0 auto;
            padding: 18px 20px 28px;
        }

        .run-strip {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            padding: 14px;
            display: grid;
            grid-template-columns: minmax(180px, 1.25fr) minmax(150px, 1fr) minmax(120px, 0.75fr) minmax(130px, 0.8fr) minmax(150px, 0.95fr) 132px;
            gap: 10px;
            margin-bottom: 12px;
        }

        .control-field {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .control-field label {
            font-size: 11px;
            color: var(--muted);
            font-weight: 650;
        }

        .control-field select,
        .control-field input {
            width: 100%;
            height: 38px;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel-muted);
            color: var(--text);
            padding: 0 11px;
            font-size: 14px;
            outline: none;
            transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
        }

        .control-field select:focus,
        .control-field input:focus {
            border-color: var(--blue);
            background: var(--panel);
            box-shadow: 0 0 0 3px var(--blue-soft);
        }

        .symbol-field {
            min-width: 190px;
        }

        .field-hint {
            min-height: 15px;
            color: var(--muted);
            font-size: 11px;
            line-height: 1.3;
        }

        .readonly-field {
            height: 38px;
            display: flex;
            align-items: center;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel-muted);
            color: var(--muted);
            padding: 0 11px;
            font-size: 13px;
        }

        .advanced-settings {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            padding: 0 14px;
            margin: -2px 0 12px;
        }

        .advanced-settings summary {
            cursor: pointer;
            color: var(--muted);
            font-size: 12px;
            font-weight: 700;
            padding: 12px 0;
        }

        .advanced-settings[open] {
            padding-bottom: 14px;
        }

        .manual-toggle {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            color: #334155;
            font-size: 13px;
            margin-right: 16px;
        }

        .control-field.compact {
            max-width: 180px;
            margin-top: 10px;
        }

        .control-field input:disabled {
            color: var(--muted-2);
            cursor: not-allowed;
        }

        .btn-primary {
            height: 38px;
            align-self: end;
            border: 0;
            border-radius: 8px;
            background: var(--blue);
            color: #ffffff;
            font-weight: 750;
            cursor: pointer;
            transition: background 0.15s, transform 0.1s;
        }

        .btn-primary:hover { background: #1e40af; }
        .btn-primary:active { transform: translateY(1px); }

        .hot-stocks-panel {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            padding: 14px;
            margin-bottom: 12px;
        }

        .section-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 12px;
        }

        .section-header h2 {
            font-size: 14px;
            font-weight: 750;
        }

        .section-header span {
            color: var(--muted);
            font-size: 12px;
        }

        .hot-stocks-grid {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 8px;
        }

        .hot-stock-card {
            min-height: 72px;
            text-align: left;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel-muted);
            padding: 10px;
            cursor: pointer;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            gap: 8px;
            transition: border-color 0.15s, background 0.15s, transform 0.1s;
        }

        .hot-stock-card:hover,
        .hot-stock-card.active {
            border-color: var(--blue);
            background: #eff6ff;
        }

        .hot-stock-card:active {
            transform: translateY(1px);
        }

        .stock-main {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 8px;
            color: var(--text);
            font-size: 13px;
            font-weight: 750;
        }

        .stock-main small {
            color: var(--muted);
            font-size: 11px;
            font-weight: 600;
        }

        .stock-meta {
            display: grid;
            grid-template-columns: auto auto;
            gap: 2px 8px;
            color: var(--muted);
            font-size: 11px;
        }

        .stock-price {
            color: var(--text);
        }

        .stock-change.positive { color: var(--green); }
        .stock-change.negative { color: var(--red); }

        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 10px;
            margin-bottom: 12px;
        }

        .metric-card {
            min-height: 74px;
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            padding: 13px 14px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .metric-label {
            color: var(--muted);
            font-size: 11px;
            font-weight: 650;
        }

        .metric-value {
            display: block;
            margin-top: 7px;
            font-size: 21px;
            line-height: 1.1;
            color: var(--text);
        }

        .metric-value.positive { color: var(--green); }
        .metric-value.negative { color: var(--red); }
        .metric-value.neutral { color: var(--blue); }

        .analysis-grid {
            display: grid;
            grid-template-columns: minmax(0, 1fr) 320px;
            gap: 12px;
            align-items: start;
        }

        .chart-card,
        .insights-panel {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            overflow: hidden;
        }

        .chart-header,
        .insights-header {
            min-height: 48px;
            border-bottom: 1px solid var(--line-soft);
            padding: 12px 14px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
        }

        .chart-header h2,
        .insights-header h2 {
            font-size: 14px;
            font-weight: 750;
        }

        .chart-header span,
        .insights-header span {
            color: var(--muted);
            font-size: 12px;
        }

        .chart-loading {
            min-height: 520px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--muted);
            font-size: 14px;
        }

        .plotly-chart {
            width: 100%;
            min-height: 680px;
        }

        .insights-panel {
            min-height: 728px;
        }

        .insights-body {
            padding: 14px;
        }

        .insight-section {
            padding: 0 0 14px;
            margin-bottom: 14px;
            border-bottom: 1px solid var(--line-soft);
        }

        .insight-section:last-child {
            border-bottom: 0;
            margin-bottom: 0;
            padding-bottom: 0;
        }

        .insight-section h3 {
            font-size: 12px;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 8px;
        }

        .insight-section p {
            color: #334155;
            font-size: 13px;
            line-height: 1.58;
        }

        .insight-list {
            display: grid;
            gap: 8px;
            list-style: none;
        }

        .insight-list li {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            color: #334155;
            font-size: 13px;
        }

        .insight-list span:first-child {
            color: var(--muted);
        }

        .risk-pill {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 5px 9px;
            background: var(--amber-soft);
            color: var(--amber);
            font-size: 12px;
            font-weight: 700;
            margin-bottom: 9px;
        }

        .data-note {
            background: var(--panel-muted);
            border: 1px solid var(--line-soft);
            border-radius: 8px;
            padding: 11px;
            color: var(--muted);
            font-size: 12px;
            line-height: 1.55;
        }

        .error-text { color: var(--red); }

        @media (max-width: 1100px) {
            .run-strip {
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }

            .btn-primary {
                grid-column: span 3;
            }

            .metrics-grid {
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }

            .hot-stocks-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .analysis-grid {
                grid-template-columns: 1fr;
            }

            .insights-panel {
                min-height: auto;
            }
        }

        @media (max-width: 720px) {
            .app-bar {
                align-items: flex-start;
                flex-direction: column;
                padding: 14px 16px;
            }

            .system-status {
                flex-wrap: wrap;
            }

            .workbench {
                padding: 12px;
            }

            .run-strip,
            .hot-stocks-grid,
            .metrics-grid {
                grid-template-columns: 1fr;
            }

            .section-header {
                align-items: flex-start;
                flex-direction: column;
            }

            .btn-primary {
                grid-column: auto;
            }

            .metric-card {
                min-height: 62px;
            }

            .metric-value {
                font-size: 19px;
            }

            .chart-header,
            .insights-header {
                align-items: flex-start;
                flex-direction: column;
            }

            .plotly-chart {
                min-height: 560px;
            }
        }
    </style>
</head>
<body>
    <div class="app-shell">
        <header class="app-bar">
            <div>
                <div class="eyebrow">Strategy Research</div>
                <h1>Quant Research Workbench</h1>
                <p>策略回测 · 模拟数据 · Plotly 交互图表</p>
            </div>
            <div class="system-status">
                <span class="status-dot"></span>
                <span>Demo data ready</span>
                <span>v0.2</span>
            </div>
        </header>

        <main class="workbench">
            <section class="run-strip" id="controls" aria-label="回测参数">
                <div class="control-field">
                    <label for="strategy">策略</label>
                    <select id="strategy">
                        <option value="ma_cross">双均线交叉</option>
                        <option value="rsi">RSI反转</option>
                        <option value="macd">MACD金叉死叉</option>
                        <option value="bollinger">布林带突破</option>
                    </select>
                </div>
                <div class="control-field symbol-field">
                    <label for="symbol">标的</label>
                    <input id="symbol" type="text" value="sh600519" oninput="scheduleSymbolLookup()">
                    <span id="symbolIdentity" class="field-hint">识别标的中...</span>
                </div>
                <div class="control-field">
                    <label for="days">数据天数</label>
                    <input id="days" type="number" value="500" min="100" max="2000">
                </div>
                <div class="control-field">
                    <label>起始价</label>
                    <div id="priceSource" class="readonly-field">自动 · 历史首日收盘价</div>
                </div>
                <div class="control-field">
                    <label for="cash">初始资金(¥)</label>
                    <input id="cash" type="number" value="100000" min="10000">
                </div>
                <button class="btn-primary" onclick="runBacktest()">运行回测</button>
            </section>

            <details id="advancedSettings" class="advanced-settings">
                <summary>高级设置</summary>
                <label class="manual-toggle">
                    <input id="manualPriceToggle" type="checkbox" onchange="toggleManualPrice()">
                    手动覆盖起始价格
                </label>
                <div class="control-field compact">
                    <label for="price">起始价格(¥)</label>
                    <input id="price" type="number" value="100" min="10" disabled>
                </div>
            </details>

            <section class="hot-stocks-panel">
                <div class="section-header">
                    <div>
                        <h2>热门 A 股</h2>
                        <span>成交额榜 Top 10，接口失败时使用备用热门池</span>
                    </div>
                    <span id="hotStocksSource">加载中</span>
                </div>
                <div id="hotStocks" class="hot-stocks-grid"></div>
            </section>

            <section id="metrics" class="metrics-grid" aria-label="核心指标"></section>

            <section id="analysisGrid" class="analysis-grid">
                <section id="chart" class="chart-card" aria-label="回测图表">
                    <div class="chart-header">
                        <div>
                            <h2>价格走势、交易信号与资产曲线</h2>
                            <span>支持缩放、悬停查看和图例切换</span>
                        </div>
                        <span id="chartStatus">等待运行</span>
                    </div>
                    <div class="chart-loading">点击“运行回测”或等待演示数据加载</div>
                </section>

                <aside id="insightsPanel" class="insights-panel" aria-label="策略洞察">
                    <div class="insights-header">
                        <div>
                            <h2>策略洞察</h2>
                            <span>等待策略结果</span>
                        </div>
                    </div>
                    <div class="insights-body">
                        <div class="data-note">演示数据加载后将显示策略逻辑、风险摘要和参数摘要。</div>
                    </div>
                </aside>
            </section>
        </main>
    </div>

    <script>
        const STRATEGY_INFO = {
            "ma_cross": { name: "双均线交叉", desc: "短期均线上穿长期均线买入，下穿卖出。经典的顺势跟踪策略。" },
            "rsi": { name: "RSI反转", desc: "RSI低于30超卖买入，高于70超买卖出。捕捉均值回归。" },
            "macd": { name: "MACD金叉死叉", desc: "MACD线上穿信号线买入，下穿卖出。最常用的趋势指标。" },
            "bollinger": { name: "布林带突破", desc: "价格跌破下轨买入，突破上轨卖出。基于波动率的均值回归策略。" },
        };

        let symbolLookupTimer = null;
        let selectedStockName = null;
        let currentDataSource = '-';
        let currentPriceSource = '自动 · 历史首日收盘价';
        window.lastMetrics = {};

        document.getElementById('strategy').addEventListener('change', function() {
            renderInsights(window.lastMetrics || {});
        });

        function formatTurnover(value) {
            const num = Number(value || 0);
            if (num >= 100000000) return (num / 100000000).toFixed(2) + '亿';
            if (num >= 10000) return (num / 10000).toFixed(2) + '万';
            return num.toFixed(0);
        }

        function scheduleSymbolLookup() {
            clearTimeout(symbolLookupTimer);
            symbolLookupTimer = setTimeout(lookupSymbol, 350);
        }

        async function lookupSymbol() {
            const symbol = document.getElementById('symbol').value;
            if (!symbol.trim()) return;

            try {
                const resp = await fetch(`/api/stock/lookup?symbol=${encodeURIComponent(symbol)}`);
                const data = await resp.json();
                selectedStockName = data.name;
                document.getElementById('symbol').value = data.symbol;
                document.getElementById('symbolIdentity').textContent =
                    data.name ? `${data.name} · ${data.symbol}` : `未匹配名称 · ${data.symbol}`;
            } catch (e) {
                selectedStockName = null;
                document.getElementById('symbolIdentity').textContent = `识别失败 · ${symbol}`;
            }
            renderInsights(window.lastMetrics || {});
        }

        async function loadHotStocks() {
            const source = document.getElementById('hotStocksSource');
            source.textContent = '加载中';
            try {
                const resp = await fetch('/api/hot-stocks?limit=10');
                const data = await resp.json();
                source.textContent = data.source === 'realtime' ? '实时成交额榜' : '备用热门池';
                renderHotStocks(data.items || []);
            } catch (e) {
                source.textContent = '加载失败';
                document.getElementById('hotStocks').innerHTML =
                    '<div class="data-note">热门股加载失败，请稍后刷新页面。</div>';
            }
        }

        function renderHotStocks(items) {
            const container = document.getElementById('hotStocks');
            container.innerHTML = '';

            items.forEach(item => {
                const card = document.createElement('button');
                card.type = 'button';
                card.className = 'hot-stock-card';
                card.dataset.symbol = item.symbol;
                card.onclick = () => selectHotStock(item);
                const cls = Number(item.change_pct || 0) >= 0 ? 'positive' : 'negative';
                card.innerHTML = `
                    <span class="stock-main">${item.name}<small>${item.symbol}</small></span>
                    <span class="stock-meta">
                        <strong class="stock-price">¥${item.latest}</strong>
                        <span class="stock-change ${cls}">${item.change_pct}%</span>
                        <small>成交额 ${formatTurnover(item.turnover)}</small>
                    </span>
                `;
                container.appendChild(card);
            });
        }

        function selectHotStock(item) {
            selectedStockName = item.name;
            document.getElementById('symbol').value = item.symbol;
            document.getElementById('symbolIdentity').textContent = `${item.name} · ${item.symbol}`;
            document.querySelectorAll('.hot-stock-card').forEach(card => {
                card.classList.toggle('active', card.dataset.symbol === item.symbol);
            });
            renderInsights(window.lastMetrics || {});
        }

        function toggleManualPrice() {
            const enabled = document.getElementById('manualPriceToggle').checked;
            document.getElementById('price').disabled = !enabled;
            currentPriceSource = enabled ? '手动覆盖' : '自动 · 历史首日收盘价';
            document.getElementById('priceSource').textContent = currentPriceSource;
            renderInsights(window.lastMetrics || {});
        }

        function describePriceSource(source, startPrice) {
            const price = startPrice ? ` · ¥${startPrice}` : '';
            if (source === 'historical_first_close') return `自动 · 历史首日收盘价${price}`;
            if (source === 'manual_override') return `手动覆盖${price}`;
            if (source === 'simulated_default') return `模拟默认${price}`;
            if (source === 'demo_seed_price') return `演示数据${price}`;
            return `自动${price}`;
        }

        function describeDataSource(source) {
            if (source === 'historical') return '真实历史行情';
            if (source === 'simulated_fallback') return '模拟 fallback';
            if (source === 'simulated_demo') return '演示模拟数据';
            return source || '-';
        }

        function renderChart(chartSpec) {
            const container = document.getElementById('chart');

            if (!window.Plotly) {
                container.innerHTML = `
                    <div class="chart-header">
                        <div>
                            <h2>价格走势、交易信号与资产曲线</h2>
                            <span class="error-text">Plotly 加载失败，请刷新页面重试</span>
                        </div>
                    </div>
                    <div class="chart-loading error-text">Plotly 加载失败</div>
                `;
                return;
            }

            let spec;
            try {
                spec = typeof chartSpec === 'string' ? JSON.parse(chartSpec) : chartSpec;
            } catch (e) {
                container.innerHTML = `
                    <div class="chart-header">
                        <div>
                            <h2>价格走势、交易信号与资产曲线</h2>
                            <span class="error-text">图表数据解析失败</span>
                        </div>
                    </div>
                    <div class="chart-loading error-text">${e.message}</div>
                `;
                return;
            }

            container.innerHTML = `
                <div class="chart-header">
                    <div>
                        <h2>价格走势、交易信号与资产曲线</h2>
                        <span>支持缩放、悬停查看和图例切换</span>
                    </div>
                    <span id="chartStatus">已更新</span>
                </div>
                <div id="plotlyChart" class="plotly-chart"></div>
            `;
            Plotly.newPlot(
                'plotlyChart',
                spec.data || [],
                spec.layout || {},
                Object.assign({ responsive: true, displaylogo: false }, spec.config || {})
            );
        }

        function metricClass(value) {
            const numVal = parseFloat(value);
            if (isNaN(numVal)) return 'neutral';
            if (numVal > 0) return 'positive';
            if (numVal < 0) return 'negative';
            return 'neutral';
        }

        function renderMetrics(metrics = {}) {
            const container = document.getElementById('metrics');
            container.innerHTML = '';

            const items = [
                { key: '年化收益率', label: '年化收益率' },
                { key: '总收益率', label: '总收益率' },
                { key: '最大回撤', label: '最大回撤' },
                { key: '胜率', label: '胜率' },
                { key: '总交易次数', label: '交易次数' },
                { key: '最终资产', label: '最终资产' },
            ];

            items.forEach(item => {
                const value = metrics[item.key] || '-';
                const card = document.createElement('div');
                card.className = 'metric-card';
                card.innerHTML = `
                    <span class="metric-label">${item.label}</span>
                    <strong class="metric-value ${metricClass(value)}">${value}</strong>
                `;
                container.appendChild(card);
            });
        }

        function renderInsights(metrics = {}) {
            const strategyId = document.getElementById('strategy').value;
            const info = STRATEGY_INFO[strategyId] || STRATEGY_INFO.ma_cross;
            const symbol = document.getElementById('symbol').value || '-';
            const days = document.getElementById('days').value || '-';
            const cash = document.getElementById('cash').value || '-';
            const identity = selectedStockName ? `${selectedStockName} · ${symbol}` : symbol;
            const maxDrawdown = metrics['最大回撤'] || '-';
            const annualReturn = metrics['年化收益率'] || '-';
            const tradeCount = metrics['总交易次数'] || '-';
            const winRate = metrics['胜率'] || '-';

            document.getElementById('insightsPanel').innerHTML = `
                <div class="insights-header">
                    <div>
                        <h2>策略洞察</h2>
                        <span>${info.name}</span>
                    </div>
                </div>
                <div class="insights-body">
                    <section class="insight-section">
                        <h3>策略逻辑</h3>
                        <p>${info.desc}</p>
                    </section>
                    <section class="insight-section">
                        <h3>风险摘要</h3>
                        <div class="risk-pill">最大回撤 ${maxDrawdown}</div>
                        <ul class="insight-list">
                            <li><span>年化收益率</span><strong>${annualReturn}</strong></li>
                            <li><span>胜率</span><strong>${winRate}</strong></li>
                            <li><span>交易次数</span><strong>${tradeCount}</strong></li>
                        </ul>
                    </section>
                    <section class="insight-section">
                        <h3>参数摘要</h3>
                        <ul class="insight-list">
                            <li><span>标的</span><strong>${identity}</strong></li>
                            <li><span>样本长度</span><strong>${days} 天</strong></li>
                            <li><span>数据来源</span><strong>${describeDataSource(currentDataSource)}</strong></li>
                            <li><span>起始价来源</span><strong>${currentPriceSource}</strong></li>
                            <li><span>初始资金</span><strong>¥${cash}</strong></li>
                        </ul>
                    </section>
                    <section class="insight-section">
                        <h3>数据说明</h3>
                        <div class="data-note">当前页面使用模拟行情数据生成回测结果，仅用于策略研究和界面演示，不构成投资建议。</div>
                    </section>
                </div>
            `;
        }

        async function runBacktest() {
            const strategy = document.getElementById('strategy').value;
            const symbol = document.getElementById('symbol').value;
            const days = document.getElementById('days').value;
            const cash = document.getElementById('cash').value;
            const manualPrice = document.getElementById('manualPriceToggle').checked;

            document.getElementById('chart').innerHTML = `
                <div class="chart-header">
                    <div>
                        <h2>价格走势、交易信号与资产曲线</h2>
                        <span>正在运行回测</span>
                    </div>
                    <span id="chartStatus">计算中</span>
                </div>
                <div class="chart-loading">运行回测中...</div>
            `;
            document.getElementById('metrics').innerHTML = '';
            renderInsights(window.lastMetrics || {});

            try {
                const params = new URLSearchParams({
                    strategy_id: strategy,
                    symbol,
                    days,
                    cash,
                    seed: '42',
                    auto_price: String(!manualPrice),
                    use_real_data: 'true',
                });
                if (manualPrice) params.set('start_price', document.getElementById('price').value);

                const resp = await fetch(`/api/backtest?${params.toString()}`);
                const data = await resp.json();
                currentDataSource = data.data_source || '-';
                currentPriceSource = describePriceSource(data.price_source, data.start_price);
                document.getElementById('priceSource').textContent = currentPriceSource;

                if (data.errors && data.errors.length > 0) {
                    document.getElementById('chart').innerHTML = `
                        <div class="chart-header">
                            <div>
                                <h2>价格走势、交易信号与资产曲线</h2>
                                <span class="error-text">回测返回错误</span>
                            </div>
                        </div>
                        <div class="chart-loading error-text">${data.errors.join(', ')}</div>
                    `;
                    renderInsights(data.metrics || {});
                    return;
                }

                window.lastMetrics = data.metrics || {};
                renderMetrics(data.metrics);
                renderInsights(data.metrics);
                renderChart(data.chart);

            } catch (e) {
                document.getElementById('chart').innerHTML = `
                    <div class="chart-header">
                        <div>
                            <h2>价格走势、交易信号与资产曲线</h2>
                            <span class="error-text">请求失败</span>
                        </div>
                    </div>
                    <div class="chart-loading error-text">${e.message}</div>
                `;
                renderInsights(window.lastMetrics || {});
            }
        }

        window.addEventListener('DOMContentLoaded', async () => {
            renderInsights();
            await loadHotStocks();
            await lookupSymbol();
            const resp = await fetch('/api/backtest/demo');
            const data = await resp.json();
            window.lastMetrics = data.metrics || {};
            currentDataSource = data.data_source || '-';
            currentPriceSource = describePriceSource(data.price_source, data.start_price);
            document.getElementById('priceSource').textContent = currentPriceSource;
            renderMetrics(data.metrics);
            renderInsights(data.metrics);
            renderChart(data.chart);
        });
    </script>
</body>
</html>
"""
