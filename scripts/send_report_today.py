#!/usr/bin/env python3
"""Send the daily report via email."""
import subprocess
import sys

report = r"""🚀 投资理财助手 — 策略生成中...

📈 *每日投资策略报告*
📅 2026-06-24 03:21

📊 *个股*
锋龙股份　¥72.81　+1.18%　📉 建议观望/减仓

📊 *基金 / ETF*
沪深300ETF　¥4.95　-2.77%　➡️ 继续持有
上证50ETF　¥3.01　-2.86%　➡️ 继续持有
红利ETF　¥3.06　-1.42%　✅ 强烈建议加仓
港股科技50ETF招商　¥0.81　+0.50%　✅ 强烈建议加仓
AI人工智能ETF平安　¥0.73　-0.27%　➡️ 继续持有
卫星ETF富国　¥1.30　-0.23%　📈 建议加仓

🔍 *信号明细*

*锋龙股份*　¥72.81　+1.18%
　布林带：⚪ 持有（中轨 64.26）
　RSI：🔴 减仓（RSI=76.9 超买）
　MACD：⚪ 多头（+1.2427）

*红利ETF*　¥3.06　-1.42%
　布林带：🟡 关注加仓（接近下轨 3.06/3.06）
　RSI：🟢 买入（RSI=17.8 超卖）
　MACD：⚪ 空头（-0.0230）

*港股科技50ETF招商*　¥0.81　+0.50%
　布林带：🟡 关注加仓（接近下轨 0.81/0.80）
　RSI：🟢 买入（RSI=20.7 超卖）
　MACD：⚪ 空头（-0.0061）

*卫星ETF富国*　¥1.30　-0.23%
　布林带：🟡 关注加仓（接近下轨 1.30/1.29）
　RSI：⚪ 持有（RSI=40.6 正常）
　MACD：⚪ 多头（+0.0008）

━━━━━━━━━━━━━━━━━━━━
📊 *定投计划*
　月定投 ¥3,000　日均 ¥136
🟢 *加仓信号*（执行日定投 + 酌情加码）：
　• 红利ETF　¥3.06
　　布林(接近下轨 3.06/3.06), RSI(RSI=17.8 超卖) → 定投 ¥205（1.5x）
　• 港股科技50ETF招商　¥0.81
　　布林(接近下轨 0.81/0.80), RSI(RSI=20.7 超卖) → 定投 ¥205（1.5x）
　• 卫星ETF富国　¥1.30
　　布林(接近下轨 1.30/1.29) → 定投 ¥205（1.5x）
🔴 *减仓信号*（回调风险）：
　• 锋龙股份　¥72.81
━━━━━━━━━━━━━━━━━━━━"""

result = subprocess.run(
    [
        "/home/yunfeixu/quant-backtest/.venv/bin/python",
        "/home/yunfeixu/quant-backtest/scripts/send_email.py",
        "--subject", "📈 上午盘中策略",
        "--to", "863221102@qq.com",
    ],
    input=report.encode("utf-8"),
    capture_output=True,
    timeout=30,
)
print("STDOUT:", result.stdout.decode("utf-8", errors="replace"))
print("STDERR:", result.stderr.decode("utf-8", errors="replace"))
sys.exit(result.returncode)
