# CPR Screening Console - Quick Start Guide

## 🚀 Run in 3 Steps

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Launch the App
```bash
streamlit run app.py
```

### Step 3: Open in Browser
Navigate to `http://localhost:8501`

---

## 📋 What You Get

- **CPR Screening Dashboard** for NSE equities
- **Configurable filters** (width, position, bias, Virgin CPR)
- **KPI summary** (scanned, matches, narrow/wide counts)
- **CSV export** for further analysis
- **Clean, research-focused interface** (no chart clutter)

---

## 🎯 First Scan

1. **Leave "Default Sample" selected** in the sidebar (15 NSE symbols pre-loaded)
2. **Keep "Use Mock Data" checked** (for testing without live connection)
3. **Click "🔄 Refresh Data"**
4. **View results** in the main table
5. **Adjust filters** to narrow down matches

---

## 🔧 Customize Symbols

### Option A: Edit Default List
- In sidebar, edit the text area under "Default Sample"
- Add/remove symbols (one per line)
- Use `.NS` suffix for NSE (e.g., `RELIANCE.NS`)

### Option B: Upload Your CSV
1. Create a CSV with symbols in first column:
   ```
   RELIANCE.NS
   TCS.NS
   INFY.NS
   ```
2. In sidebar, select "Upload CSV"
3. Upload your file

---

## 📊 Understand the Output

### Key Columns
- **CPR Bottom / Pivot / CPR Top**: The three CPR levels
- **Width %**: CPR Width as % of previous close (Narrow ≤0.25%, Wide ≥0.75%)
- **Bias**: Bullish (Pivot > BC), Bearish (Pivot < BC), or Neutral
- **Position**: Where current price is relative to CPR
- **Virgin CPR**: Bullish/Bearish Virgin or Developing (can change before close)
- **Data Status**: OK, Stale, Delayed, or Data unavailable

### Color Coding
- 🟢 Green: Bullish conditions
- 🔴 Red: Bearish conditions
- 🟠 Orange: Developing/Neutral
- ⚫ Gray: Unavailable data

---

## ⚠️ Important Notes

- **Mock Data Mode**: Enabled by default for testing. Disable in Perplexity environment.
- **NSE Coverage**: Indian equities may have delayed/incomplete data in free sources.
- **Not Investment Advice**: For research only. Verify with licensed data before trading.
- **No Real-Time Alerts**: Manual refresh required.

---

## 🛠️ Troubleshooting

### "No symbols loaded"
- Add symbols via sidebar (Default Sample, Paste CSV, or Upload CSV)

### "Data unavailable"
- Check symbol format (use `.NS` for NSE)
- Mock data mode may not have real data for all symbols
- In Perplexity environment, disable mock data and use live connector

### App won't start
- Ensure Python 3.9+ is installed
- Run `pip install -r requirements.txt`
- Check that port 8501 is not in use

---

## 📚 Next Steps

1. **Review README.md** for full documentation
2. **Run tests**: `python test_cpr.py`
3. **Customize filters** for your strategy
4. **Export results** to CSV for chart preparation
5. **Integrate licensed data** (see README "Upgrade Path")

---

## 📞 Need Help?

- Check the **Methodology panel** in the app for formulas
- Review **test_cpr.py** for usage examples
- Read **README.md** for detailed documentation

**Remember**: This is a research tool. Always verify with licensed data before trading.