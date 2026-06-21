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

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.sim_data import generate_stock_data, STRATEGY_DESCRIPTIONS, get_demo_result
from backtest.engine import run_backtest
from strategies.ma_cross import MovingAverageCrossStrategy
from strategies.rsi import RSIStrategy
from strategies.macd import MACDStrategy
from strategies.bollinger import BollingerBandsStrategy

# App 配置
pio.templates.default = "plotly_dark"

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


def build_chart(data: pd.DataFrame, result) -> str:
    """
    生成完整的回测图表 HTML

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
        template="plotly_dark",
        height=900,
        dragmode="zoom",
        hovermode="x unified",
        margin=dict(l=40, r=20, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis3_rangeslider_visible=False,
    )

    fig.update_xaxes(title_text="日期", row=3, col=1)
    fig.update_yaxes(title_text="价格", row=1, col=1)
    fig.update_yaxes(title_text="成交量", row=2, col=1)
    fig.update_yaxes(title_text="资产(¥)", row=3, col=1)

    return fig.to_html(include_plotlyjs=True, full_html=False)


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


@app.get("/api/backtest")
async def run_backtest_api(
    strategy_id: str = Query("ma_cross", description="策略ID"),
    symbol: str = Query("sh600519", description="股票代码"),
    days: int = Query(500, description="数据天数", ge=100, le=2000),
    start_price: float = Query(100, description="起始价格", ge=10),
    cash: float = Query(100000, description="初始资金"),
    seed: int = Query(42, description="随机种子"),
):
    """运行回测并返回结果"""
    if strategy_id not in STRATEGY_MAP:
        raise HTTPException(400, f"不支持的策略: {strategy_id}，可选: {list(STRATEGY_MAP.keys())}")

    # 生成模拟数据
    data = generate_stock_data(symbol=symbol, days=days,
                                start_price=start_price, seed=seed)

    # 创建策略
    cls = STRATEGY_MAP[strategy_id]
    strategy = cls()

    # 运行回测
    result = run_backtest(data, strategy, initial_capital=cash)

    # 生成图表
    chart_html = build_chart(data, result)

    return {
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

    results = []
    for sid in ids:
        cls = STRATEGY_MAP[sid]
        strategy = cls()
        result = run_backtest(data, strategy)
        results.append({
            "id": sid,
            "name": STRATEGY_DESCRIPTIONS[sid]["name"],
            "metrics": result.summary(),
        })

    # 对比图
    fig = go.Figure()
    for r in results:
        # 这里简化，实际应该重新跑一次拿 equity_curve
        pass

    fig.update_layout(template="plotly_dark", height=500,
                      title="策略净值对比")
    fig.add_hline(y=100000, line_dash="dash", line_color="gray")

    return {
        "results": results,
    }


_PAGE_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>量化回测系统</title>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f0f1a;
            color: #e0e0e0;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #1a1a3e 0%, #0f0f1a 100%);
            padding: 20px 40px;
            border-bottom: 1px solid #2a2a4a;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .header h1 { font-size: 22px; color: #FFD700; }
        .header span { color: #888; font-size: 13px; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        
        .controls {
            background: #1a1a3e;
            border: 1px solid #2a2a4a;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
        }
        .control-group { display: flex; flex-direction: column; gap: 6px; }
        .control-group label { font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; }
        .control-group select,
        .control-group input {
            background: #0f0f1a;
            border: 1px solid #2a2a4a;
            color: #e0e0e0;
            padding: 10px 12px;
            border-radius: 8px;
            font-size: 14px;
            outline: none;
            transition: border-color 0.2s;
        }
        .control-group select:focus,
        .control-group input:focus { border-color: #FFD700; }
        .control-group select option { background: #1a1a3e; }
        
        .btn {
            background: linear-gradient(135deg, #FFD700, #FFA000);
            color: #1a1a3e;
            border: none;
            padding: 10px 24px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.1s, opacity 0.2s;
            align-self: flex-end;
        }
        .btn:hover { opacity: 0.9; transform: translateY(-1px); }
        .btn:active { transform: translateY(0); }
        .btn-secondary {
            background: #2a2a4a;
            color: #e0e0e0;
        }

        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 12px;
            margin-bottom: 20px;
        }
        .metric-card {
            background: #1a1a3e;
            border: 1px solid #2a2a4a;
            border-radius: 10px;
            padding: 16px;
            text-align: center;
        }
        .metric-card .label { font-size: 11px; color: #888; text-transform: uppercase; margin-bottom: 6px; }
        .metric-card .value { font-size: 20px; font-weight: bold; }
        .metric-card .value.positive { color: #26a69a; }
        .metric-card .value.negative { color: #ef5350; }
        .metric-card .value.neutral { color: #FFD700; }

        .chart-container {
            background: #1a1a3e;
            border: 1px solid #2a2a4a;
            border-radius: 12px;
            padding: 16px;
            overflow: hidden;
        }
        .chart-container .chart-loading {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 500px;
            color: #888;
            font-size: 16px;
        }
        .chart-container iframe { width: 100%; border: none; }

        .strategy-desc {
            background: #1a1a3e;
            border: 1px solid #2a2a4a;
            border-radius: 10px;
            padding: 16px 20px;
            margin-bottom: 20px;
            font-size: 14px;
            color: #aaa;
            line-height: 1.6;
        }
        .strategy-desc strong { color: #FFD700; }

        .footer {
            text-align: center;
            padding: 30px;
            color: #555;
            font-size: 12px;
        }

        @media (max-width: 768px) {
            .controls { grid-template-columns: 1fr 1fr; }
            .metrics-grid { grid-template-columns: repeat(3, 1fr); }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📈 量化回测系统</h1>
        <span>v0.2 | 模拟数据演示</span>
    </div>

    <div class="container">
        <div class="controls" id="controls">
            <div class="control-group">
                <label>策略</label>
                <select id="strategy">
                    <option value="ma_cross">双均线交叉</option>
                    <option value="rsi">RSI反转</option>
                    <option value="macd">MACD金叉死叉</option>
                    <option value="bollinger">布林带突破</option>
                </select>
            </div>
            <div class="control-group">
                <label>股票代码</label>
                <input id="symbol" type="text" value="sh600519">
            </div>
            <div class="control-group">
                <label>数据天数</label>
                <input id="days" type="number" value="500" min="100" max="2000">
            </div>
            <div class="control-group">
                <label>起始价格(¥)</label>
                <input id="price" type="number" value="100" min="10">
            </div>
            <div class="control-group">
                <label>初始资金(¥)</label>
                <input id="cash" type="number" value="100000" min="10000">
            </div>
            <div class="control-group">
                <label>&nbsp;</label>
                <button class="btn" onclick="runBacktest()">🚀 运行回测</button>
            </div>
        </div>

        <div id="strategyDesc" class="strategy-desc">
            💡 选择一个策略，点击「运行回测」查看结果。数据由模拟生成，无需网络。
        </div>

        <div id="metrics" class="metrics-grid"></div>

        <div id="chart" class="chart-container">
            <div class="chart-loading">点击「运行回测」开始</div>
        </div>

        <div class="footer">
            数据仅为模拟演示，不构成投资建议。回测结果不代表未来表现。
        </div>
    </div>

    <script>
        const STRATEGY_INFO = {
            "ma_cross": { name: "双均线交叉", desc: "短期均线上穿长期均线买入，下穿卖出。经典的顺势跟踪策略。" },
            "rsi": { name: "RSI反转", desc: "RSI低于30超卖买入，高于70超买卖出。捕捉均值回归。" },
            "macd": { name: "MACD金叉死叉", desc: "MACD线上穿信号线买入，下穿卖出。最常用的趋势指标。" },
            "bollinger": { name: "布林带突破", desc: "价格跌破下轨买入，突破上轨卖出。基于波动率的均值回归策略。" },
        };

        document.getElementById('strategy').addEventListener('change', function() {
            const info = STRATEGY_INFO[this.value];
            document.getElementById('strategyDesc').innerHTML =
                '<strong>' + info.name + '</strong> — ' + info.desc;
        });

        async function runBacktest() {
            const strategy = document.getElementById('strategy').value;
            const symbol = document.getElementById('symbol').value;
            const days = document.getElementById('days').value;
            const price = document.getElementById('price').value;
            const cash = document.getElementById('cash').value;

            document.getElementById('chart').innerHTML =
                '<div class="chart-loading">⏳ 运行回测中...</div>';
            document.getElementById('metrics').innerHTML = '';

            try {
                const resp = await fetch(
                    `/api/backtest?strategy_id=${strategy}&symbol=${symbol}&days=${days}&start_price=${price}&cash=${cash}&seed=42`
                );
                const data = await resp.json();

                if (data.errors && data.errors.length > 0) {
                    document.getElementById('chart').innerHTML =
                        '<div class="chart-loading" style="color:#ef5350;">❌ ' + data.errors.join(', ') + '</div>';
                    return;
                }

                // 渲染指标卡片
                renderMetrics(data.metrics);

                // 渲染图表
                document.getElementById('chart').innerHTML = data.chart;

                // 重绘Plotly图表
                if (window.Plotly) {
                    const graphs = document.querySelectorAll('#chart .js-plotly-plot');
                    graphs.forEach(g => Plotly.react(g));
                }

            } catch (e) {
                document.getElementById('chart').innerHTML =
                    '<div class="chart-loading" style="color:#ef5350;">❌ 请求失败: ' + e.message + '</div>';
            }
        }

        function renderMetrics(metrics) {
            const container = document.getElementById('metrics');
            container.innerHTML = '';

            const items = [
                { key: '年化收益率', label: '年化收益率' },
                { key: '总收益率', label: '总收益率' },
                { key: '最大回撤', label: '最大回撤' },
                { key: '夏普比率', label: '夏普比率' },
                { key: '索提诺比率', label: '索提诺比率' },
                { key: '卡玛比率', label: '卡玛比率' },
                { key: '总交易次数', label: '交易次数' },
                { key: '胜率', label: '胜率' },
                { key: '最终资产', label: '最终资产' },
                { key: '年化波动率', label: '年化波动率' },
            ];

            items.forEach(item => {
                let value = metrics[item.key] || '-';
                let cls = 'neutral';

                // 判断正负
                const numVal = parseFloat(value);
                if (!isNaN(numVal)) {
                    if (numVal > 0) cls = 'positive';
                    else if (numVal < 0) cls = 'negative';
                }

                const card = document.createElement('div');
                card.className = 'metric-card';
                card.innerHTML = `
                    <div class="label">${item.label}</div>
                    <div class="value ${cls}">${value}</div>
                `;
                container.appendChild(card);
            });
        }

        // 初始加载演示数据
        window.addEventListener('DOMContentLoaded', async () => {
            const resp = await fetch('/api/backtest/demo');
            const data = await resp.json();
            renderMetrics(data.metrics);
            document.getElementById('chart').innerHTML = data.chart;
            document.getElementById('strategyDesc').innerHTML =
                '<strong>双均线交叉</strong> — 短期均线上穿长期均线买入，下穿卖出。经典的顺势跟踪策略。';
        });
    </script>
</body>
</html>
"""
