"""
回测引擎 V2 — 支持滑点、税费、T+1、涨跌停限制
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from config.rules import (
    DEFAULT_COMMISSION, DEFAULT_STAMP_TAX, DEFAULT_TRANSFER_FEE,
    MIN_COMMISSION, NORMAL_LIMIT_PCT, T_PLUS_1, MIN_TRADE_UNIT,
    DEFAULT_SLIPPAGE,
)
from backtest.metrics import calculate_metrics


@dataclass
class TradeRecord:
    """单笔交易记录"""
    date: pd.Timestamp
    direction: str               # "buy" / "sell"
    price: float                 # 成交价（含滑点）
    shares: int                  # 成交股数
    cost: float                  # 交易总成本
    commission: float = 0.0      # 佣金
    stamp_tax: float = 0.0       # 印花税
    transfer_fee: float = 0.0    # 过户费
    slippage: float = 0.0        # 滑点成本
    reason: str = ""             # 触发原因


@dataclass
class BacktestResult:
    """完整的回测结果"""
    initial_capital: float = 0
    final_value: float = 0
    cash: float = 0
    positions: dict = field(default_factory=dict)
    equity_curve: pd.Series = None
    trade_log: List[TradeRecord] = field(default_factory=list)
    daily_positions: pd.DataFrame = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def summary(self) -> Dict[str, Any]:
        """返回可打印的摘要"""
        return {
            "初始资金": f"¥{self.initial_capital:,.2f}",
            "最终资产": f"¥{self.final_value:,.2f}",
            "现金余额": f"¥{self.cash:,.2f}",
            "持仓市值": f"¥{sum(self.positions.values()):,.2f}",
            "总收益率": f"{self.metrics.get('总收益率', 0):.2%}",
            "年化收益率": f"{self.metrics.get('年化收益率', 0):.2%}",
            "最大回撤": f"{self.metrics.get('最大回撤', 0):.2%}",
            "夏普比率": f"{self.metrics.get('夏普比率', 0):.2f}",
            "索提诺比率": f"{self.metrics.get('索提诺比率', 0):.2f}",
            "卡玛比率": f"{self.metrics.get('卡玛比率', 0):.2f}",
            "年化波动率": f"{self.metrics.get('年化波动率', 0):.2%}",
            "总交易次数": self.metrics.get("总交易次数", 0),
            "胜率": f"{self.metrics.get('胜率', 0):.2%}",
            "盈亏比": f"{self.metrics.get('盈亏比', 0):.2f}",
        }


def simulate_trade(
    direction: str,
    price: float,
    shares: int,
    date: pd.Timestamp,
    slippage_pct: float = DEFAULT_SLIPPAGE,
    commission_pct: float = DEFAULT_COMMISSION,
    stamp_tax_pct: float = DEFAULT_STAMP_TAX,
    transfer_fee_pct: float = DEFAULT_TRANSFER_FEE,
) -> TradeRecord:
    """
    模拟一笔交易，计算实际成交价和费用

    参数:
        direction: "buy" / "sell"
        price: 信号触发时的价格
        shares: 股数
        date: 交易日期
        slippage_pct: 滑点比例
        commission_pct: 佣金比例
        stamp_tax_pct: 印花税比例（仅卖出）
        transfer_fee_pct: 过户费比例

    返回: TradeRecord
    """
    # 实际成交价（考虑滑点）
    if direction == "buy":
        actual_price = price * (1 + slippage_pct)
    else:  # sell
        actual_price = price * (1 - slippage_pct)

    notional = actual_price * shares

    # 佣金（有最低5元限制）
    commission = max(notional * commission_pct, MIN_COMMISSION)

    # 过户费（买卖都收）
    transfer_fee = notional * transfer_fee_pct

    # 印花税（仅卖出收）
    stamp_tax = notional * stamp_tax_pct if direction == "sell" else 0

    # 总交易成本
    total_cost = commission + stamp_tax + transfer_fee

    return TradeRecord(
        date=date,
        direction=direction,
        price=round(actual_price, 3),
        shares=shares,
        cost=round(notional + total_cost if direction == "buy" else notional - total_cost, 2),
        commission=round(commission, 2),
        stamp_tax=round(stamp_tax, 2),
        transfer_fee=round(transfer_fee, 2),
        slippage=round(abs(actual_price - price) * shares, 2),
    )


def run_backtest(
    data: pd.DataFrame,
    strategy,
    initial_capital: float = 100000,
    commission_pct: float = DEFAULT_COMMISSION,
    stamp_tax_pct: float = DEFAULT_STAMP_TAX,
    transfer_fee_pct: float = DEFAULT_TRANSFER_FEE,
    slippage_pct: float = DEFAULT_SLIPPAGE,
    enable_limit: bool = True,
    enable_t1: bool = T_PLUS_1,
    benchmark_data: Optional[pd.DataFrame] = None,
    max_position_pct: float = 1.0,
) -> BacktestResult:
    """
    运行回测（V2 引擎）

    参数:
        data: 行情数据（columns: date, open, high, low, close, volume）
        strategy: 策略实例（必须实现 generate_signals 方法）
        initial_capital: 初始资金
        commission_pct: 佣金比例
        stamp_tax_pct: 印花税比例
        transfer_fee_pct: 过户费比例
        slippage_pct: 滑点比例
        enable_limit: 是否启用涨跌停限制
        enable_t1: 是否启用 T+1 限制
        benchmark_data: 基准数据（用于计算 Alpha/Beta）
        max_position_pct: 单只股票最大仓位比例

    返回: BacktestResult
    """
    result = BacktestResult()
    result.initial_capital = initial_capital

    # 生成交易信号
    df = strategy.generate_signals(data)
    if "trade_signal" not in df.columns:
        result.errors.append("策略未生成 trade_signal 列")
        return result

    # ===== 模拟交易 =====
    cash = initial_capital
    position = 0            # 持仓股数
    last_buy_date = None    # T+1 记录上次买入日期
    equity_curve = []
    daily_positions = []

    # 涨停价/跌停价计算（基于昨收）
    df["prev_close"] = df["close"].shift(1)
    df["limit_up"] = df["prev_close"] * (1 + NORMAL_LIMIT_PCT)
    df["limit_down"] = df["prev_close"] * (1 - NORMAL_LIMIT_PCT)

    for i in range(len(df)):
        row = df.iloc[i]
        signal = row["trade_signal"]
        price = row["close"]
        date = row["date"]

        can_sell_today = True
        can_buy_today = True

        # T+1 限制：今天不能卖今天买的
        if enable_t1 and last_buy_date is not None and date == last_buy_date:
            can_sell_today = False

        # 涨跌停限制：涨停买不进，跌停卖不出
        if enable_limit:
            if price >= row["limit_up"] * 0.995:  # 接近涨停（留0.5%容差）
                can_buy_today = False
            if price <= row["limit_down"] * 1.005:  # 接近跌停
                can_sell_today = False

        # === 卖出信号 ===
        if signal == -1 and position > 0 and can_sell_today:
            trade = simulate_trade(
                direction="sell",
                price=price,
                shares=position,
                date=date,
                slippage_pct=slippage_pct,
                commission_pct=commission_pct,
                stamp_tax_pct=stamp_tax_pct,
                transfer_fee_pct=transfer_fee_pct,
            )
            cash += trade.cost
            position = 0
            result.trade_log.append(trade)

        # === 买入信号 ===
        if signal == 1 and can_buy_today:
            # 计算可用资金和最大可买股数
            max_buy_cash = cash * max_position_pct
            max_shares = int(max_buy_cash / price / MIN_TRADE_UNIT) * MIN_TRADE_UNIT

            if max_shares >= MIN_TRADE_UNIT:
                trade = simulate_trade(
                    direction="buy",
                    price=price,
                    shares=max_shares,
                    date=date,
                    slippage_pct=slippage_pct,
                    commission_pct=commission_pct,
                    stamp_tax_pct=stamp_tax_pct,
                    transfer_fee_pct=transfer_fee_pct,
                )
                cash -= trade.cost
                position = max_shares
                last_buy_date = date
                result.trade_log.append(trade)

        # 记录每日资产
        total_value = cash + position * price
        equity_curve.append(total_value)
        daily_positions.append({"date": date, "cash": cash, "shares": position, "value": total_value})

    # ===== 计算绩效 =====
    result.cash = cash
    result.positions = {strategy.name if hasattr(strategy, "name") else "stock": position}
    result.final_value = equity_curve[-1] if equity_curve else initial_capital
    result.equity_curve = pd.Series(equity_curve, index=df["date"])
    result.daily_positions = pd.DataFrame(daily_positions)

    # 基准曲线（用于 Alpha/Beta）
    benchmark_curve = None
    if benchmark_data is not None:
        if "close" in benchmark_data.columns:
            benchmark_curve = pd.Series(
                benchmark_data["close"].values,
                index=pd.to_datetime(benchmark_data["date"]),
            )

    result.metrics = calculate_metrics(
        equity_curve=result.equity_curve,
        benchmark_curve=benchmark_curve,
        trade_log=[
            {
                "type": t.direction,
                "price": t.price,
                "shares": t.shares,
                "cost": t.cost if t.direction == "buy" else 0,
                "revenue": t.cost if t.direction == "sell" else 0,
            }
            for t in result.trade_log
        ],
    )

    return result
