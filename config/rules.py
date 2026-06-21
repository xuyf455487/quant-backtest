"""
A股交易规则常量
"""

# 交易时间
MARKET_OPEN = "09:30"
MARKET_CLOSE = "15:00"
MORNING_CLOSE = "11:30"
AFTERNOON_OPEN = "13:00"

# 交易规则
T_PLUS_1 = True           # T+1 规则
MIN_TRADE_UNIT = 100       # 最小交易单位（1手=100股）
PRICE_TICK = 0.01          # A股最小价格变动单位

# 涨跌停限制（主板）
ST_LIMIT_PCT = 0.05        # ST/*ST 股票 ±5%
NORMAL_LIMIT_PCT = 0.10    # 普通股票 ±10%
KCB_LIMIT_PCT = 0.20       # 科创板 ±20%
CYB_LIMIT_PCT = 0.20       # 创业板 ±20%

# 默认费率（A股）
DEFAULT_COMMISSION = 0.00025   # 佣金 万2.5（最低5元）
DEFAULT_STAMP_TAX = 0.001      # 印花税 千1（仅卖出）
DEFAULT_TRANSFER_FEE = 0.00001 # 过户费 万0.1
MIN_COMMISSION = 5.0           # 最低佣金 5元

# 默认滑点
DEFAULT_SLIPPAGE = 0.001       # 默认滑点 千1
