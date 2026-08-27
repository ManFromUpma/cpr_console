# CPR Screening Console

A clean, practical Central Pivot Range (CPR) screening console for equities. Designed for research and chart preparation — **not** personalized investment advice.

![CPR Console](https://img.shields.io/badge/Version-1.0-blue)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ⚠️ Important Disclaimers

- **Research Use Only**: This tool is for educational and research purposes.
- **Not Investment Advice**: Do not use for live trading decisions without verification.
- **Data Limitations**: Free data sources may be delayed, rate-limited, or incomplete.
- **NSE Coverage**: Indian equities (.NS) may have limited coverage compared to US markets.
- **No Guarantees**: No guarantee of data accuracy, completeness, or timeliness.

---

## 📋 Features

- **CPR Calculation**: Pivot, BC, TC, CPR Top/Bottom, Width, Width %
- **Screening Filters**:
  - CPR Width (Narrow/Wide/Custom)
  - Price Position (Above/Below/Inside/Near CPR)
  - Previous-Session Bias (Bullish/Bearish/Neutral)
  - Virgin CPR (Bullish/Bearish/Developing)
  - Liquidity filters (price, volume, market cap)
  - Trend confirmation (SMA20, SMA50)
- **Dashboard**:
  - KPI row (scanned, matches, narrow/wide counts, Virgin counts)
  - Sortable results table with color coding
  - CSV export
  - Methodology panel with formulas and timestamps
- **Data Quality**:
  - Distinguishes OK, Stale, Delayed, Unavailable
  - Handles missing data gracefully
  - Configurable session timezone

---

## 🧰 Mac Tinker Lab

This repository also includes a **54-tool MacBook tinkering lab**: individually runnable Python utilities for system observation, storage and metadata exploration, networking, launchd/plist inspection, developer-workspace hygiene, text and data experiments, image metadata, local logs, Spotlight, and small macOS automation exercises. The tools are safe-by-default and documented with beginner analogies plus deeper technical explanations.

Start with the [Mac Tinker Lab guide](MAC_TINKER_GUIDE.md), browse the [tool catalog](mac_tinker/tool_catalog.txt), or run a tool directly:

```bash
python3 tools/system_snapshot.py
python3 tools/large_files.py ~/Downloads --count 10
python3 tools/unicode_inspector.py "café ☕"
```

The lab does not replace the CPR Console or change its market-data behavior.

---

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- pip (Python package manager)

### Installation

1. **Clone or download** this repository

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   streamlit run app.py
   ```

4. **Open in browser**: The app will open at `http://localhost:8501`

---

## 📁 File Structure

```
cpr_console/
├── app.py                  # Main Streamlit dashboard
├── cpr_engine.py           # CPR calculation and screening logic
├── data_provider.py        # Data source adapter (Perplexity Finance / Mock)
├── requirements.txt        # Python dependencies
├── sample_symbols.csv      # Sample NSE symbols
├── test_cpr.py             # CPR unit tests
├── test_mac_tinker.py      # Mac Tinker Lab smoke tests
├── MAC_TINKER_GUIDE.md     # Layman guide and deep dives
├── mac_tinker/             # Shared helpers and importable tool modules
└── tools/                  # Individually runnable tool wrappers
```

---

## 🎯 How to Use

### 1. Load Symbols

**Option A: Default Sample**
- Uses pre-loaded NSE symbols (RELIANCE.NS, TCS.NS, etc.)
- Editable in the sidebar text area

**Option B: Paste CSV**
- Paste symbols directly (one per line or first column of CSV)
- Example:
  ```
  RELIANCE.NS
  TCS.NS
  INFY.NS
  ```

**Option C: Upload CSV**
- Upload a CSV file with symbols in the first column
- Use `sample_symbols.csv` as a template

### 2. Configure Filters

In the "Screening Filters" section:

- **CPR Width**: Choose Any, Narrow (≤0.25%), Wide (≥0.75%), or Custom range
- **Price Position**: Filter by Above/Below/Inside/Near CPR
- **Previous Bias**: Bullish, Bearish, Neutral, or Any
- **Virgin CPR**: Bullish Virgin, Bearish Virgin, Any Virgin, or Any
- **Liquidity**: Set minimum price and volume thresholds

### 3. Run Scan

- Click "🔄 Refresh Data" to fetch latest data
- Results appear in the main table
- KPI row shows summary statistics

### 4. Export Results

- Click "📥 Download Results (CSV)" to export filtered results
- Use for further analysis or chart preparation

---

## 🔧 Configuration

### Exchange & Universe

- **Default**: NSE (National Stock Exchange of India)
- **Supported**: NSE, BSE, NYSE, NASDAQ, Custom
- **Symbol Format**: Use `.NS` suffix for NSE (e.g., `RELIANCE.NS`)

### Session Timezone

- **Default**: Asia/Kolkata (for NSE)
- **Options**: America/New_York, Europe/London, etc.

### Data Source

- **Mock Data** (default): For testing without live connection
- **Perplexity Finance**: In Perplexity environment (uncomment in `data_provider.py`)
- **Custom**: Replace `data_provider.py` with your broker's API

---

## 🧠 Professional Expert Review

The repository includes a review-only professional expertise agent that evaluates architecture, data quality, CPR/timeframe correctness, look-ahead protection, backtesting assumptions, efficiency, testing, CI/publication, security, and AI transparency. It does not fetch live market data, place trades, modify source files, or deploy anything.

Run it from the repository root:

```bash
python3 run_expert_review.py .
```

This writes `expert_review_report.md` and `expert_review_evidence.json`. The evidence collector summarizes generated CSV archives instead of sending their full contents into analysis. Findings include severity, confidence, affected files, evidence, recommendations, effort, priority, and acceptance criteria. See `EXPERT_REVIEW_AGENT.md` for details. The implemented hardening is documented in `TECHNICAL_HARDENING_DOCUMENTATION.md` and `LAYMAN_HARDENING_GUIDE.md`.

## 🧪 Testing

Run unit tests:

```bash
python test_cpr.py
```

Expected output:
```
=== CPR Formula Validation ===
Input: High=110, Low=100, Close=106

Pivot = 105.3333333333 (expected: 105.333333...)
BC = 105.0000000000 (expected: 105.00)
TC = 105.6666666667 (expected: 105.666666...)
CPR Bottom = 105.0000000000 (expected: 105.00)
CPR Top = 105.6666666667 (expected: 105.666666...)
CPR Width = 0.6666666667 (expected: 0.666666...)
CPR Width % = 0.6289308176% (expected: ~0.6289%)

✓ All CPR formula validations PASSED
```

---

## 📊 CPR Formulas

Using previous completed session's High (H), Low (L), Close (C):

| Metric | Formula |
|--------|---------|
| Pivot | (H + L + C) / 3 |
| BC (Bottom Central) | (H + L) / 2 |
| TC (Top Central) | 2 × Pivot − BC |
| CPR Top | max(BC, TC) |
| CPR Bottom | min(BC, TC) |
| CPR Width | CPR Top − CPR Bottom |
| CPR Width % | (CPR Width / Previous Close) × 100 |

### Bias Detection

- **Bullish**: Pivot > BC
- **Bearish**: Pivot < BC
- **Neutral**: Pivot = BC

### Virgin CPR

- **Bullish Virgin**: Current session Low > CPR Top
- **Bearish Virgin**: Current session High < CPR Bottom
- **Developing**: Virgin condition during open session (can change before close)

---

## 🔌 Data Provider Adapter

The `data_provider.py` module provides a clean adapter interface. To integrate a licensed broker feed:

1. Create a new class implementing the same interface as `PerplexityFinanceDataProvider`
2. Implement `fetch_ohlcv()` and `fetch_multiple_symbols()` methods
3. Return `OHLCVData` objects with proper metadata
4. Update `get_data_provider()` factory function

Example adapter structure:

```python
class MyBrokerDataProvider:
    def __init__(self, session_timezone="Asia/Kolkata"):
        self.session_timezone = pytz.timezone(session_timezone)
    
    def fetch_ohlcv(self, symbol, start_date, end_date, interval="1day"):
        # Your broker's API call here
        df = ...  # DataFrame with columns: open, high, low, close, volume
        return OHLCVData(symbol, df, "My Broker", datetime.now())
    
    def fetch_multiple_symbols(self, symbols, lookback_days=60):
        return {sym: self.fetch_ohlcv(sym, ...) for sym in symbols}
```

---

## ⚠️ Known Limitations

### Data Quality

- **NSE Coverage**: Indian equities may have delayed or incomplete data
- **Intraday Data**: Current session data may be approximate or unavailable
- **Corporate Actions**: Splits, dividends, and bonuses may not be perfectly adjusted
- **Rate Limits**: Free data sources enforce request limits

### Functionality

- **No Real-Time Alerts**: Manual refresh required
- **No Persistent Storage**: Results not saved between sessions
- **No Chart Overlays**: CPR lines not drawn on charts (by design)
- **No Backtesting**: Historical screening not implemented

### Technical

- **Streamlit Required**: Must run locally or on Streamlit Cloud
- **Python Dependencies**: Requires pip installation
- **No Docker**: Containerization not provided

---

## 🛠️ Upgrade Path to Licensed Data

To upgrade to a licensed broker-data source:

1. **Choose a Provider**:
   - Zerodha Kite Connect (India)
   - Upstox API (India)
   - Alpha Vantage (Global, free tier available)
   - Yahoo Finance API (unofficial, rate-limited)
   - Broker-specific APIs (Fyers, Angel One, etc.)

2. **Replace Data Provider**:
   - Create new adapter in `data_provider.py`
   - Implement authentication and rate-limit handling
   - Ensure OHLCV data format matches expectations

3. **Add Real-Time Features** (optional):
   - WebSocket streaming for live updates
   - Alert system (email, SMS, webhook)
   - Background scheduler for periodic scans

4. **Deploy**:
   - Streamlit Cloud (free for public repos)
   - Heroku, AWS, or GCP for private deployment
   - Docker container for portability

---

## 📝 Changelog

### v1.0 (2026-08-13)
- Initial release
- CPR calculation and screening
- Streamlit dashboard
- Mock data provider for testing
- Unit tests for CPR formulas
- CSV export functionality

---

## 📄 License

MIT License — Free for personal and commercial use.

---

## 🙏 Acknowledgments

- CPR methodology: [Zerodha Varsity](https://zerodha.com/varsity/chapter/the-central-pivot-range/)
- Inspired by TradingView CPR indicators
- Built with Streamlit, Pandas, and NumPy

---

## 📞 Support

For issues or questions:
- Check the `test_cpr.py` file for usage examples
- Review the methodology panel in the app
- Verify data source limitations in `data_provider.py`

**Remember**: This is a research tool. Always verify with licensed data before making trading decisions.