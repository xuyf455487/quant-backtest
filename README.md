# 📈 量化回测系统

股票和基金回测软件 — 基于 Python，支持 A 股 / 基金 / 美股。

## 快速开始

```bash
# 1. 激活虚拟环境
source .venv/bin/activate

# 2. 运行交互式回测
python run.py

# 3. 启动 Web 可视化界面
uvicorn web.app:app --reload
# 访问 http://localhost:8000
```

## 项目结构

```
quant-backtest/
├── data/
│   ├── raw/              # 原始行情数据
│   └── processed/        # 清洗后数据
├── strategies/           # 交易策略
│   ├── base.py           # 策略基类
│   └── ma_cross.py       # 双均线交叉策略（示例）
├── backtest/             # 回测引擎
│   └── engine.py         # 回测核心逻辑 + 绩效计算
├── web/                  # Web 可视化
│   └── app.py            # FastAPI + Plotly
├── config/
│   └── settings.py       # 配置文件
├── scripts/
│   └── fetch_data.py     # 数据获取（akshare/yfinance）
├── notebooks/            # Jupyter 探索性分析
└── run.py                # CLI 入口
```

## 支持的策略

| 策略 | 文件 | 说明 |
|------|------|------|
| 双均线交叉 | `strategies/ma_cross.py` | MA5 上穿 MA20 买入，下穿卖出 |

## 数据来源

| 来源 | 覆盖范围 |
|------|---------|
| [akshare](https://github.com/akfamily/akshare) | A 股、基金、期货（免费开源） |
| [yfinance](https://github.com/ranaroussi/yfinance) | 美股、港股 |

## 技术栈

- **Python 3.9+** — 核心语言
- **pandas / numpy** — 数据处理
- **backtrader** — 回测框架
- **akshare** — A 股行情数据
- **FastAPI** — Web 服务
- **Plotly** — 交互式图表
- **Streamlit** — 数据看板（备选）

## 核心指标

- 总收益率 / 年化收益率
- 最大回撤
- 夏普比率
- 胜率
- 交易次数

## 自定义策略

```python
from strategies.base import Strategy

class MyStrategy(Strategy):
    def generate_signals(self, data):
        df = data.copy()
        # 你的策略逻辑
        df["trade_signal"] = 0  # 1=买入, -1=卖出, 0=持有
        return df
```

## 使用 Hermes Skill

开发前加载回测工作流：

```
skill_view("quant-backtest-workflow")
skill_view("quant-data-pipeline")
```

---

**工欲善其事，必先利其器。** 🚀
