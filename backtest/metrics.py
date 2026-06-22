"""
绩效指标计算 — 全面的风险/收益评估
"""

import numpy as np
import pandas as pd
from typing import Optional


def calculate_metrics(equity_curve: pd.Series, 
                      benchmark_curve: Optional[pd.Series] = None,
                      risk_free_rate: float = 0.02,
                      trade_log: list = None) -> dict:
    """
    计算全面的绩效指标

    参数:
        equity_curve: 每日总资产序列（index=日期）
        benchmark_curve: 基准每日净值序列（可选）
        risk_free_rate: 无风险利率（默认2%）
        trade_log: 交易记录列表

    返回:
        指标字典
    """
    metrics = {}
    daily_returns = equity_curve.pct_change().dropna()
    total_days = len(daily_returns)
    trading_days_per_year = 252

    if total_days < 2:
        return {"error": "数据点太少，无法计算"}

    years = total_days / trading_days_per_year
    initial = equity_curve.iloc[0]
    final = equity_curve.iloc[-1]
    total_return = (final - initial) / initial

    # === 基础指标 ===
    metrics["总收益率"] = total_return
    metrics["年化收益率"] = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
    metrics["累计收益"] = final - initial

    # === 风险指标 ===
    # 年化波动率
    metrics["年化波动率"] = daily_returns.std() * np.sqrt(trading_days_per_year)

    # 最大回撤
    peak = equity_curve.expanding().max()
    drawdown = (equity_curve - peak) / peak
    metrics["最大回撤"] = drawdown.min()
    
    # 最大回撤持续期（最长的从峰到谷的天数）
    is_drawdown = drawdown < 0
    drawdown_periods = []
    current_len = 0
    for dd in is_drawdown:
        if dd:
            current_len += 1
        else:
            if current_len > 0:
                drawdown_periods.append(current_len)
                current_len = 0
    if current_len > 0:
        drawdown_periods.append(current_len)
    metrics["最长回撤天数"] = max(drawdown_periods) if drawdown_periods else 0
    metrics["回撤恢复天数"] = _calc_recovery_days(drawdown)

    # 最大回撤区间
    max_dd_idx = drawdown.idxmin()
    if pd.notna(max_dd_idx):
        peak_before = equity_curve[:max_dd_idx].idxmax()
        metrics["最大回撤区间"] = f"{peak_before.date()} ~ {max_dd_idx.date()}"
    else:
        metrics["最大回撤区间"] = "无"

    # 下行波动率（只考虑亏损的波动）
    negative_returns = daily_returns[daily_returns < 0]
    metrics["下行波动率"] = negative_returns.std() * np.sqrt(trading_days_per_year) if len(negative_returns) > 0 else 0

    # === 风险调整收益 ===
    excess_returns = daily_returns.mean() * trading_days_per_year - risk_free_rate

    # 夏普比率
    if daily_returns.std() > 0:
        metrics["夏普比率"] = (daily_returns.mean() * trading_days_per_year - risk_free_rate) / (daily_returns.std() * np.sqrt(trading_days_per_year))
    else:
        metrics["夏普比率"] = 0

    # 索提诺比率（只考虑下行风险）
    if metrics["下行波动率"] > 0:
        metrics["索提诺比率"] = excess_returns / metrics["下行波动率"]
    else:
        metrics["索提诺比率"] = 0

    # 卡玛比率（年化/最大回撤）
    if metrics["最大回撤"] < 0:
        metrics["卡玛比率"] = metrics["年化收益率"] / abs(metrics["最大回撤"])
    else:
        metrics["卡玛比率"] = float('inf')

    # === 交易统计 ===
    if trade_log:
        metrics["总交易次数"] = len(trade_log)
        
        buys = [t for t in trade_log if t.get("type") in ("buy", "买入")]
        sells = [t for t in trade_log if t.get("type") in ("sell", "卖出")]
        
        metrics["买入次数"] = len(buys)
        metrics["卖出次数"] = len(sells)

        # 胜率：盈利交易占比
        if len(sells) > 0 and len(buys) > 0:
            # 配对买卖
            paired_wins = 0
            paired_total = min(len(buys), len(sells))
            for i in range(paired_total):
                buy_price = buys[i].get("price", 0)
                sell_price = sells[i].get("price", 0)
                if sell_price > buy_price:
                    paired_wins += 1
            metrics["胜率"] = paired_wins / paired_total if paired_total > 0 else 0

        # 平均盈亏比
        if len(sells) > 0 and len(buys) > 0:
            profits = []
            for i in range(min(len(buys), len(sells))):
                pnl = (sells[i].get("revenue", 0) - buys[i].get("cost", 0)) / buys[i].get("cost", 1)
                profits.append(pnl)
            if profits:
                win_profits = [p for p in profits if p > 0]
                loss_profits = [p for p in profits if p < 0]
                avg_win = np.mean(win_profits) if win_profits else 0
                avg_loss = abs(np.mean(loss_profits)) if loss_profits else 1
                metrics["盈亏比"] = avg_win / avg_loss if avg_loss > 0 else 0

    # === Alpha / Beta（需要基准） ===
    if benchmark_curve is not None:
        # 对齐到相同时间索引
        aligned = pd.concat([daily_returns, benchmark_curve.pct_change()], axis=1, join="inner")
        aligned.columns = ["strategy", "benchmark"]
        aligned = aligned.dropna()

        if len(aligned) > 10:
            cov = np.cov(aligned["strategy"], aligned["benchmark"])
            metrics["Beta"] = cov[0, 1] / cov[1, 1] if cov[1, 1] > 0 else 0
            metrics["Alpha"] = (aligned["strategy"].mean() - metrics["Beta"] * aligned["benchmark"].mean()) * trading_days_per_year
            metrics["R平方"] = (cov[0, 1] ** 2) / (cov[0, 0] * cov[1, 1]) if cov[0, 0] * cov[1, 1] > 0 else 0

    return metrics


def _calc_recovery_days(drawdown_series: pd.Series) -> int:
    """计算从最大回撤中恢复所需的天数"""
    max_dd = drawdown_series.min()
    if max_dd >= 0:
        return 0
    max_dd_idx = drawdown_series.idxmin()
    after_dd = drawdown_series.loc[max_dd_idx:]
    recovery = after_dd[after_dd >= 0]
    if not recovery.empty:
        return (recovery.index[0] - max_dd_idx).days
    return (drawdown_series.index[-1] - max_dd_idx).days
