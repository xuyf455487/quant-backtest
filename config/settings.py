"""回测系统配置"""
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# 回测参数
BACKTEST_CONFIG = {
    "default_cash": 100000,        # 默认初始资金
    "default_commission": 0.0003,  # 默认佣金（万三）
    "default_slippage": 0.001,     # 默认滑点
}

# 数据配置
DATA_CONFIG = {
    "akshare_try_count": 3,        # 数据获取重试次数
    "cache_enabled": True,         # 是否缓存数据
    "default_start": "2020-01-01", # 默认回测起始日期
}

# A股交易规则
TRADING_RULES = {
    "market_open": "09:30",
    "market_close": "15:00",
    "t_plus_1": True,              # T+1 规则
    "min_trade_unit": 100,         # 最小交易单位（手）
}
