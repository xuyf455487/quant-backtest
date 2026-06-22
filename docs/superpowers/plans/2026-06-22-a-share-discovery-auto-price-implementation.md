# A Share Discovery Auto Price Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add A-share hot stock discovery, stock name lookup, and automatic start price handling to the Web backtest UI.

**Architecture:** Keep the current FastAPI single-file Web app. Add small pure helper functions in `web/app.py` for symbol normalization, fallback hot stocks, hot stock payload construction, lookup payload construction, and dataset preparation; expose them through new API routes and wire the existing vanilla JS UI to those APIs.

**Tech Stack:** Python, FastAPI, pandas, akshare, existing `portfolio.data.fetch_hist`, Plotly, vanilla HTML/CSS/JavaScript, custom Python test runner.

---

## File Structure

- Modify `web/app.py`
  - Add `Optional` import.
  - Import `fetch_hist` from `portfolio.data`.
  - Add fallback hot stock constants and helper functions.
  - Add `/api/hot-stocks` and `/api/stock/lookup`.
  - Update `/api/backtest` to support `auto_price`, optional `start_price`, and real-data-first behavior.
  - Update `_PAGE_HTML` with hot stock cards, symbol identity display, price source display, advanced manual price controls, and updated request building.
- Modify `tests/test_web.py`
  - Add tests for fallback hot stocks, symbol lookup, auto-price dataset preparation, and page HTML containers.
  - Keep existing Plotly JSON and workbench layout tests.

## Task 1: Pure Data Helpers

**Files:**
- Modify: `web/app.py`
- Test: `tests/test_web.py`

- [ ] **Step 1: Write failing tests**

Update imports in `tests/test_web.py`:

```python
from web.app import (
    _PAGE_HTML,
    build_chart,
    build_compare_payload,
    build_hot_stocks_payload,
    build_stock_lookup_payload,
    normalize_a_share_symbol,
    prepare_backtest_dataset,
)
```

Add tests:

```python
def test_normalize_a_share_symbol_adds_market_prefix():
    assert normalize_a_share_symbol("600519") == "sh600519"
    assert normalize_a_share_symbol("000001") == "sz000001"
    assert normalize_a_share_symbol("300750") == "sz300750"
    assert normalize_a_share_symbol("sh600036") == "sh600036"


def test_hot_stocks_payload_falls_back_when_fetcher_fails():
    def failing_fetcher():
        raise RuntimeError("network unavailable")

    payload = build_hot_stocks_payload(fetcher=failing_fetcher, limit=3)

    assert payload["source"] == "fallback"
    assert len(payload["items"]) == 3
    assert payload["items"][0]["symbol"].startswith(("sh", "sz", "bj"))
    assert {"symbol", "code", "name", "latest", "change_pct", "turnover"} <= set(payload["items"][0])


def test_stock_lookup_uses_fallback_name_for_known_symbol():
    payload = build_stock_lookup_payload("600519", hot_stock_fetcher=lambda: (_ for _ in ()).throw(RuntimeError("offline")))

    assert payload["symbol"] == "sh600519"
    assert payload["code"] == "600519"
    assert payload["name"] == "贵州茅台"
    assert payload["source"] == "fallback"


def test_prepare_backtest_dataset_uses_historical_first_close_for_auto_price():
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
```

Add these tests to `run_tests()`.

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'; python tests\test_web.py
```

Expected: import errors because helper functions do not exist yet.

- [ ] **Step 3: Implement helper functions**

In `web/app.py`, add:

```python
from typing import Callable, Optional
```

Add this import:

```python
from portfolio.data import fetch_hist
```

Add fallback stock data:

```python
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
```

Add helpers:

```python
def normalize_a_share_symbol(symbol: str) -> str:
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
    return normalized, normalized[2:] if normalized[:2] in ("sh", "sz", "bj") else normalized


def _fallback_hot_stocks(limit: int = 10) -> list[dict]:
    return FALLBACK_HOT_STOCKS[:limit]
```

Implement `build_hot_stocks_payload()` using `ak.stock_zh_a_spot_em()`:

```python
def build_hot_stocks_payload(fetcher: Optional[Callable[[], pd.DataFrame]] = None, limit: int = 10) -> dict:
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
```

Implement lookup:

```python
def build_stock_lookup_payload(symbol: str, hot_stock_fetcher: Optional[Callable[[], pd.DataFrame]] = None) -> dict:
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
    return {"symbol": normalized, "code": code, "name": None, "latest": None, "source": "unknown"}
```

Implement dataset preparation:

```python
def prepare_backtest_dataset(
    symbol: str,
    days: int,
    start_price: Optional[float],
    auto_price: bool = True,
    use_real_data: bool = True,
    seed: int = 42,
    hist_fetcher: Callable[[str, int], pd.DataFrame] = fetch_hist,
) -> tuple[pd.DataFrame, dict]:
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
```

- [ ] **Step 4: Run tests to verify helpers pass**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'; python tests\test_web.py
```

Expected: helper tests pass; later API/UI tests are not present yet.

## Task 2: API Routes and Backtest Metadata

**Files:**
- Modify: `web/app.py`
- Test: `tests/test_web.py`

- [ ] **Step 1: Write failing tests for API-facing payloads**

Add tests:

```python
def test_backtest_dataset_manual_override_uses_simulation_price():
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
```

Add to `run_tests()`.

- [ ] **Step 2: Run tests**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'; python tests\test_web.py
```

Expected: pass if Task 1 implementation is correct.

- [ ] **Step 3: Add API routes**

Add:

```python
@app.get("/api/hot-stocks")
async def hot_stocks(limit: int = Query(10, ge=1, le=30)):
    """获取A股成交额热门股，失败时返回内置备用列表"""
    return build_hot_stocks_payload(limit=limit)


@app.get("/api/stock/lookup")
async def stock_lookup(symbol: str = Query(..., description="股票代码")):
    """解析A股股票名称和规范代码"""
    return build_stock_lookup_payload(symbol)
```

- [ ] **Step 4: Update `/api/backtest` signature and body**

Change parameters:

```python
start_price: Optional[float] = Query(None, description="手动起始价格", ge=10),
auto_price: bool = Query(True, description="是否自动使用历史首日价格"),
use_real_data: bool = Query(True, description="是否优先使用真实历史行情"),
```

Replace data generation with:

```python
data, data_meta = prepare_backtest_dataset(
    symbol=symbol,
    days=days,
    start_price=start_price,
    auto_price=auto_price,
    use_real_data=use_real_data,
    seed=seed,
)
```

Add response fields:

```python
"symbol": data_meta["symbol"],
"data_source": data_meta["data_source"],
"price_source": data_meta["price_source"],
"start_price": data_meta["start_price"],
```

- [ ] **Step 5: Update `/api/backtest/demo` response metadata**

Return:

```python
"symbol": "sh600519",
"data_source": "simulated_demo",
"price_source": "demo_seed_price",
"start_price": round(float(data["close"].iloc[0]), 2),
```

- [ ] **Step 6: Run tests**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'; python tests\test_web.py
```

Expected: all Web tests pass.

## Task 3: Front-End Hot Stocks and Auto Price UI

**Files:**
- Modify: `web/app.py`
- Test: `tests/test_web.py`

- [ ] **Step 1: Write failing page HTML test**

Add:

```python
def test_page_html_includes_stock_discovery_controls():
    """测试页面包含热门股、股票身份和高级起始价控件"""
    assert 'id="hotStocks"' in _PAGE_HTML
    assert 'id="symbolIdentity"' in _PAGE_HTML
    assert 'id="priceSource"' in _PAGE_HTML
    assert 'id="advancedSettings"' in _PAGE_HTML
    assert 'id="manualPriceToggle"' in _PAGE_HTML
    assert "loadHotStocks" in _PAGE_HTML
    assert "lookupSymbol" in _PAGE_HTML
```

Add to `run_tests()`.

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'; python tests\test_web.py
```

Expected: failure because new HTML controls are not implemented.

- [ ] **Step 3: Update HTML parameter area**

In `_PAGE_HTML`, replace the symbol field with:

```html
<div class="control-field symbol-field">
  <label for="symbol">标的</label>
  <input id="symbol" type="text" value="sh600519" oninput="scheduleSymbolLookup()">
  <span id="symbolIdentity" class="field-hint">识别标的中...</span>
</div>
```

Remove the always-visible `price` control from `run-strip` and add:

```html
<div class="control-field">
  <label>起始价</label>
  <div id="priceSource" class="readonly-field">自动 · 历史首日收盘价</div>
</div>
```

Add advanced settings below `run-strip`:

```html
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
```

Add hot stocks section above metrics:

```html
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
```

- [ ] **Step 4: Add CSS**

Add CSS classes:

```css
.field-hint
.readonly-field
.advanced-settings
.manual-toggle
.control-field.compact
.hot-stocks-panel
.section-header
.hot-stocks-grid
.hot-stock-card
.hot-stock-card:hover
.hot-stock-card.active
.stock-main
.stock-meta
.stock-price
.stock-change.positive
.stock-change.negative
```

- [ ] **Step 5: Add JavaScript functions**

Add:

```javascript
let symbolLookupTimer = null;
let selectedStockName = null;
let currentDataSource = '-';
let currentPriceSource = '自动 · 历史首日收盘价';

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
  const resp = await fetch(`/api/stock/lookup?symbol=${encodeURIComponent(symbol)}`);
  const data = await resp.json();
  selectedStockName = data.name;
  document.getElementById('symbol').value = data.symbol;
  document.getElementById('symbolIdentity').textContent =
    data.name ? `${data.name} · ${data.symbol}` : `未匹配名称 · ${data.symbol}`;
  renderInsights(window.lastMetrics || {});
}

async function loadHotStocks() {
  const resp = await fetch('/api/hot-stocks?limit=10');
  const data = await resp.json();
  document.getElementById('hotStocksSource').textContent =
    data.source === 'realtime' ? '实时成交额榜' : '备用热门池';
  renderHotStocks(data.items || []);
}

function renderHotStocks(items) {
  const container = document.getElementById('hotStocks');
  container.innerHTML = '';
  items.forEach(item => {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = 'hot-stock-card';
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
  renderInsights(window.lastMetrics || {});
}

function toggleManualPrice() {
  const enabled = document.getElementById('manualPriceToggle').checked;
  document.getElementById('price').disabled = !enabled;
  document.getElementById('priceSource').textContent = enabled ? '手动覆盖' : '自动 · 历史首日收盘价';
}
```

- [ ] **Step 6: Update `runBacktest()` request**

Build query params with `URLSearchParams`:

```javascript
const manualPrice = document.getElementById('manualPriceToggle').checked;
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
```

After success:

```javascript
window.lastMetrics = data.metrics;
currentDataSource = data.data_source || '-';
currentPriceSource = data.price_source || '-';
document.getElementById('priceSource').textContent = describePriceSource(data.price_source, data.start_price);
```

Add:

```javascript
function describePriceSource(source, startPrice) {
  const price = startPrice ? ` · ¥${startPrice}` : '';
  if (source === 'historical_first_close') return `自动 · 历史首日收盘价${price}`;
  if (source === 'manual_override') return `手动覆盖${price}`;
  if (source === 'simulated_default') return `模拟默认${price}`;
  if (source === 'demo_seed_price') return `演示数据${price}`;
  return `自动${price}`;
}
```

- [ ] **Step 7: Update `renderInsights()`**

Include selected stock identity, `currentDataSource`, and `currentPriceSource` in the insights panel.

- [ ] **Step 8: Load hot stocks on DOMContentLoaded**

Call:

```javascript
await loadHotStocks();
await lookupSymbol();
```

before demo metrics/chart render or immediately after initial render.

- [ ] **Step 9: Run Web tests**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'; python tests\test_web.py
```

Expected: all Web tests pass.

## Task 4: Verification

**Files:**
- Modify only if verification exposes a defect.

- [ ] **Step 1: Run full suite**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'; python tests\run_all.py
```

Expected: all tests pass.

- [ ] **Step 2: Start local server**

Run or restart:

```powershell
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000 --lifespan off
```

Expected: server responds on `http://127.0.0.1:8000/`.

- [ ] **Step 3: Verify new APIs**

Run:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/hot-stocks?limit=3'
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/stock/lookup?symbol=600519'
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/backtest?strategy_id=ma_cross&symbol=600519&days=120&cash=100000&auto_price=true&use_real_data=false'
```

Expected:

- hot stocks returns `source` and three `items`
- lookup returns `symbol: sh600519`
- backtest returns `data_source`, `price_source`, and `start_price`

- [ ] **Step 4: Browser check**

Open `http://127.0.0.1:8000/` and confirm:

- “热门 A 股” panel renders.
- `sh600519` displays a stock name.
- start price hint says automatic by default.
- advanced settings can enable manual start price.
- running backtest without manual price works.

- [ ] **Step 5: Commit**

Run:

```powershell
git add web\app.py tests\test_web.py docs\superpowers\specs\2026-06-22-a-share-discovery-auto-price-design.md docs\superpowers\plans\2026-06-22-a-share-discovery-auto-price-implementation.md
git commit -m "feat: 增加A股热门标的和自动起始价计划"
```
