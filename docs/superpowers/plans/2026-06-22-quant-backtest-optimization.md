# Quant Backtest Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve correctness, reliability, and usability of the quant backtest project across the engine, strategies, data layer, Web API, portfolio monitor, and project tooling.

**Architecture:** Keep the existing simple package layout. Add narrowly scoped helper functions where behavior needs to be shared or tested, and avoid replacing the engine wholesale. Each task adds regression tests before changing production behavior.

**Tech Stack:** Python, pandas, numpy, FastAPI, Plotly, akshare, yfinance, PyYAML.

---

### Task 1: Core Backtest Accuracy

**Files:**
- Modify: `backtest/metrics.py`
- Modify: `backtest/engine.py`
- Modify: `tests/test_engine.py`
- Create: `requirements.txt`
- Modify: `README.md`

- [x] Add failing tests for `buy` / `sell` trade statistics and overspending cash on buys.
- [x] Fix trade direction recognition in metrics.
- [x] Make buy sizing account for slippage and fees before subtracting cash.
- [x] Make the test runner return a non-zero exit code on failures.
- [x] Add dependency list and align README with actual code.
- [x] Verify with `python tests/test_engine.py`, `python -m compileall .`, and `git diff --check`.

### Task 2: Engine Order Sizing and Position Updates

**Files:**
- Modify: `backtest/engine.py`
- Modify: `strategies/dca.py`
- Modify: `tests/test_engine.py`

- [x] Add failing tests for fixed-amount DCA buys, accumulating positions, and partial sells.
- [x] Support optional `trade_amount` for buy signals.
- [x] Support optional `sell_pct` for sell signals, defaulting to full liquidation.
- [x] Accumulate shares on additional buys instead of replacing the existing position.
- [x] Update `DCAStrategy` to emit `trade_amount`.
- [x] Verify engine tests.

### Task 3: Strategy Signal Hygiene

**Files:**
- Modify: `strategies/rsi.py`
- Modify: `strategies/bollinger.py`
- Modify: `strategies/ma_cross.py`
- Modify: `tests/test_engine.py`

- [x] Add failing tests proving RSI and Bollinger strategies only trade on threshold crossings.
- [x] Add parameter validation for moving-average windows.
- [x] Change RSI and Bollinger signals from repeated level signals to crossing signals.
- [x] Verify strategy tests.

### Task 4: Data Normalization

**Files:**
- Modify: `scripts/fetch_data.py`
- Create: `tests/test_data.py`
- Create: `tests/run_all.py`
- Modify: `README.md`

- [x] Add tests for normalizing close-only fund data to OHLCV format.
- [x] Add a reusable `normalize_ohlcv` helper.
- [x] Make fund data return `date/open/high/low/close/volume`.
- [x] Add an all-tests runner so new test files are included.
- [x] Verify all tests through the runner.

### Task 5: Web Strategy Comparison

**Files:**
- Modify: `web/app.py`
- Create or modify: `tests/test_web.py`

- [x] Extract pure comparison data generation from `/api/compare`.
- [x] Add tests that compare multiple strategy equity curves on simulated data.
- [x] Return chart HTML and per-strategy metrics from `/api/compare`.
- [x] Verify tests without requiring a running server.

### Task 6: Portfolio Monitor Reliability

**Files:**
- Modify: `portfolio/monitor.py`
- Modify: `portfolio/alerts.py` if needed
- Create or modify: `tests/test_portfolio.py`

- [x] Add tests for trading-session time checks.
- [x] Add tests proving price alerts trigger when current prices are available.
- [x] Replace inline trading-time condition with a tested helper.
- [x] Pass fetched asset results to `check_alerts` instead of an empty list.
- [x] Verify all tests.

### Task 7: Final Project Verification

**Files:**
- Modify: `README.md` if commands change

- [x] Run the full local test suite.
- [x] Run `python -m compileall .`.
- [x] Run `git diff --check`.
- [x] Review `git diff --stat` and summarize changed files.
