# Web UI Research Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the single-page backtest UI as a professional research workbench with a right-side insights panel.

**Architecture:** Keep the current FastAPI and inline `_PAGE_HTML` approach. The backend API and Plotly JSON rendering stay intact; the implementation changes page structure, CSS, front-end rendering functions, and the chart visual template.

**Tech Stack:** Python, FastAPI, Plotly, vanilla HTML/CSS/JavaScript, existing custom Python test runner.

---

## File Structure

- Modify `web/app.py`
  - Change Plotly defaults and figure layouts from dark to light workbench styling.
  - Replace the current demo-like `_PAGE_HTML` with the approved research workbench layout.
  - Add front-end `renderInsights()` and update `renderMetrics()`.
  - Preserve `renderChart()` and `Plotly.newPlot()`.
- Modify `tests/test_web.py`
  - Add a regression test that asserts the page includes the new workbench containers and does not use the old demo title/layout as the main UI.
  - Keep the existing Plotly JSON tests.

## Task 1: Page Structure Regression Test

**Files:**
- Modify: `tests/test_web.py`

- [ ] **Step 1: Write the failing test**

Add `_PAGE_HTML` to the imports:

```python
from web.app import _PAGE_HTML, build_chart, build_compare_payload
```

Add this test:

```python
def test_page_html_uses_research_workbench_layout():
    """测试页面使用研究工作台布局和右侧洞察栏"""
    assert "Quant Research Workbench" in _PAGE_HTML
    assert 'class="app-shell"' in _PAGE_HTML
    assert 'id="insightsPanel"' in _PAGE_HTML
    assert 'id="analysisGrid"' in _PAGE_HTML
    assert "function renderInsights" in _PAGE_HTML
    assert "Plotly.newPlot" in _PAGE_HTML
    assert "量化回测系统" not in _PAGE_HTML
```

Add the new test to `run_tests()`.

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'; python tests\test_web.py
```

Expected: failure because current `_PAGE_HTML` still contains the old demo UI and lacks `app-shell`, `insightsPanel`, `analysisGrid`, and `renderInsights`.

## Task 2: Research Workbench UI Implementation

**Files:**
- Modify: `web/app.py`

- [ ] **Step 1: Update Plotly light styling**

Change:

```python
pio.templates.default = "plotly_dark"
```

to:

```python
pio.templates.default = "plotly_white"
```

In `build_compare_payload()` and `build_chart()`, replace `template="plotly_dark"` with `template="plotly_white"` and set white/transparent backgrounds:

```python
paper_bgcolor="rgba(0,0,0,0)",
plot_bgcolor="#ffffff",
font=dict(color="#111827"),
```

- [ ] **Step 2: Replace page shell and layout**

Replace the old header/container stack with this structure inside `_PAGE_HTML`:

```html
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
    <section class="run-strip" id="controls">...</section>
    <section id="metrics" class="metrics-grid"></section>
    <section id="analysisGrid" class="analysis-grid">
      <div id="chart" class="chart-card">...</div>
      <aside id="insightsPanel" class="insights-panel">...</aside>
    </section>
  </main>
</div>
```

Keep the existing inputs and button IDs: `strategy`, `symbol`, `days`, `price`, `cash`, and `runBacktest()`.

- [ ] **Step 3: Replace CSS with workbench styling**

Define CSS for:

```css
:root
.app-shell
.app-bar
.system-status
.workbench
.run-strip
.control-field
.btn-primary
.metrics-grid
.metric-card
.analysis-grid
.chart-card
.chart-header
.plotly-chart
.insights-panel
.insight-section
.insight-list
.data-note
@media (max-width: 1100px)
@media (max-width: 720px)
```

Use a light gray page background, white panels, 8-10px radius, restrained blue/green/red/amber accents, and no decorative gradients.

## Task 3: Front-End Rendering Functions

**Files:**
- Modify: `web/app.py`

- [ ] **Step 1: Update `renderMetrics()` to show six core metrics**

Use this item list:

```javascript
const items = [
  { key: '年化收益率', label: '年化收益率' },
  { key: '总收益率', label: '总收益率' },
  { key: '最大回撤', label: '最大回撤' },
  { key: '胜率', label: '胜率' },
  { key: '总交易次数', label: '交易次数' },
  { key: '最终资产', label: '最终资产' },
];
```

Render each card as:

```javascript
card.innerHTML = `
  <span class="metric-label">${item.label}</span>
  <strong class="metric-value ${cls}">${value}</strong>
`;
```

- [ ] **Step 2: Add `renderInsights()`**

Add a front-end function that reads the current strategy info and form values and fills `#insightsPanel`:

```javascript
function renderInsights(metrics = {}) {
  const strategyId = document.getElementById('strategy').value;
  const info = STRATEGY_INFO[strategyId];
  const symbol = document.getElementById('symbol').value;
  const days = document.getElementById('days').value;
  const cash = document.getElementById('cash').value;
  const maxDrawdown = metrics['最大回撤'] || '-';
  const annualReturn = metrics['年化收益率'] || '-';

  document.getElementById('insightsPanel').innerHTML = `...`;
}
```

The rendered sections must include:

- `策略逻辑`
- `风险摘要`
- `参数摘要`
- `数据说明`

- [ ] **Step 3: Call `renderInsights()` on all relevant state changes**

Call it:

- after strategy selection changes
- after demo data loads
- after a successful backtest response
- when a backtest request fails, using current values where metrics are unavailable

## Task 4: Verification

**Files:**
- Modify: no source files unless a verification failure identifies a defect

- [ ] **Step 1: Run Web tests**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'; python tests\test_web.py
```

Expected: all Web tests pass.

- [ ] **Step 2: Run full test suite**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'; python tests\run_all.py
```

Expected: all tests pass.

- [ ] **Step 3: Start local server and verify HTML/API**

Run `uvicorn web.app:app --host 127.0.0.1 --port 8000 --lifespan off` in a persistent process, then verify:

```powershell
Invoke-WebRequest -Uri 'http://127.0.0.1:8000/' -UseBasicParsing
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/backtest/demo'
```

Expected:

- root page returns HTTP 200
- page contains `Quant Research Workbench`
- demo API returns `chart` JSON that starts with `{`
- demo API chart does not contain `<script`

- [ ] **Step 4: Browser visual check**

Open `http://127.0.0.1:8000/` and confirm:

- top run strip is visible
- six KPI cards are visible
- chart renders in the left/main panel
- right insights panel is visible
- no obvious text overlap at desktop width
