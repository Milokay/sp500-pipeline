# S&P 500 Portfolio Decision-Making Tool

A Python tool that combines DCF valuation, relative valuation, and Bollinger Bands technical analysis to generate buy/sell signals for all S&P 500 stocks. Outputs a professionally formatted Excel workbook.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Analyze 5 test tickers
python main.py --tickers AAPL,MSFT,JPM,XOM,PG

# Full S&P 500 analysis
python main.py

# Force refresh cached data
python main.py --refresh
```

## Output

Excel reports are generated in `data/output/` with sheets:
1. **Dashboard** - Full analysis with signals for all stocks
2. **Strong Buys** - Filtered view of BUY/STRONG BUY signals
3. **Sector Summary** - Aggregated sector-level metrics
4. **Data Quality** - Tickers with incomplete data
5. **Assumptions** - Model parameters used

## Data Source

Uses yfinance (free, no API key required). Can be configured for FMP or Polygon in `config.py`.
