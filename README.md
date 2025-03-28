# Options-Technical Hybrid Scanner

A trading tool designed for retail traders to identify and execute trades in volatile stocks by combining options data and technical analysis.

## Overview

The Options-Technical Hybrid Scanner is a trading tool designed to empower retail traders by providing a systematic, data-driven method to identify trading opportunities in volatile stocks, such as TSLA. It implements the "Options-Technical Hybrid Strategy" framework, which combines options data and technical analysis.

## Features

- **Market Context Analysis**: Evaluate market environment using technical indicators and options data
- **Key Levels Mapping**: Use options chain data to pinpoint critical support and resistance levels
- **Trade Setup Rules Engine**: Define conditions for bullish, bearish, or neutral trade setups
- **Confirmation and Timing**: Provide entry and exit signals
- **Risk Management**: Offer risk control suggestions
- **Scanner Feature**: Filter stocks using technical indicators and advanced options metrics (Gamma, GEX, Volume, OI). Uses concurrent processing for faster scans.
- **Advanced Options Metrics**: Analyze gamma, charm, vanna, vomma, VWIV, and GEX using data primarily from Interactive Brokers (via `ib_insync`), falling back to FMP and yfinance.
- **Social Media Sentiment Analysis**: Incorporate sentiment from configured sources (Twitter, Reddit, StockTwits), including historical trend analysis (In Progress)
- **Alerts System**: Define custom alert conditions via UI fields (Symbol, Setup, Confidence), trigger notifications (Email, Webhook placeholders), manage alerts via the web UI, and view triggered alert history.
- **Enhanced Visualizations**: Includes historical EMA chart, scatter plots for key levels and risk/reward, GEX profile chart, and second-order Greeks chart. All analysis charts support zoom and pan. Numerical display of key options metrics (GEX, VWIV, Max Pain) added.
- **Interactive Dashboard**: Sortable results table, sparklines for quick price action view, and clickable setup lists to filter the main results table.

## Data Sources Priority (Options)

1.  **Interactive Brokers (IBKR):** Requires running TWS/Gateway, API enabled, and relevant market data subscriptions. Uses `ib_insync`.
2.  **Financial Modeling Prep (FMP):** Requires a valid API key in `config.json` with options data access.
3.  **yfinance:** Used as a final fallback; options data (especially Greeks) may be limited or delayed.

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/options-technical-hybrid-scanner.git
cd options-technical-hybrid-scanner
python -m venv .venv
.venv\Scripts\activate.ps1

# Install dependencies
# Ensure you have the necessary API keys/credentials configured in config.json
# Ensure TWS/Gateway is running if using IBKR
.venv\Scripts\python.exe -m pip install -r requirements.txt

# Create cache directory
mkdir data_cache
```

## Configuration (`config.json`, `user_alerts.json`, `alert_history.json`)

- **`config.json`**: Configure general settings (like `max_workers` for concurrent scanning), API keys (FMP, Twitter, Reddit), IBKR connection, sentiment sources, and default alert settings (email server, webhook URL).
- **`user_alerts.json`**: Stores user-defined alert rules (created/deleted via the UI).
- **`alert_history.json`**: Stores a history of triggered alerts (viewable in the UI).

## Data Caching System

The scanner implements an intelligent caching system to optimize performance and minimize API calls:

### Cache Configuration
- **Location**: `./data_cache/` (JSON files)
- **Market Hours**: 9:30 AM - 4:00 PM ET (configurable)
- **Refresh Logic**:
  - During market hours:
    - Max 3 fresh fetches per trading day
    - 1 hour cache duration between refreshes
  - After market close:
    - Uses cached data until next market open
    - Automatically clears expired data

### Cached Data Types
1. **Market Data**:
   - NASDAQ constituents list
   - Historical price data
   - Volume/price trends

2. **Options Data**:
   - Options chains (Source: IBKR > FMP > yfinance)
   - Implied volatility
   - Open interest (Note: May be limited from IBKR depending on setup)
   - Greeks (delta, gamma, vega, theta)
   - Advanced metrics (charm, vanna, vomma)

3. **Technical Indicators**:
   - EMA/RSI calculations
   - Support/resistance levels
   - Volume profiles

4. **Sentiment Data**:
   - Current sentiment scores per source (Twitter, Reddit, StockTwits) using VADER.
   - Historical sentiment scores (stored daily in `data_cache/sentiment_history/`)

### Cache Management
```python
from src.utils.data_cache import DataCache
cache = DataCache(
    cache_dir='custom_cache',  # Optional custom location
    max_fresh_fetches=5,       # Adjust refresh rate
    market_open_time=(9, 30),  # Custom market open
    market_close_time=(16, 0)  # Custom market close
)
```

### Maintenance
- To clear cache: Delete the `data_cache` folder (including `sentiment_history`)
- Cache files are automatically pruned after 7 days
- Debug logs show cache hits/misses and data source used.
```

## Usage

```bash
# Ensure TWS/Gateway is running if using IBKR
# Ensure config.json has API keys

# Run the scanner
python src/main.py

# Run the scanner with web interface
python src/main.py --web

# Analyze a specific symbol
python src/main.py --symbol TSLA

# Test advanced options metrics
python test_options_metrics.py --symbol TSLA
```

## Advanced Options Metrics

The scanner now includes advanced options metrics analysis through the `OptionsMetricsAnalyzer` module, prioritizing IBKR data:

```python
from src.modules.options_metrics import OptionsMetricsAnalyzer

# Initialize analyzer
analyzer = OptionsMetricsAnalyzer('TSLA')

# Calculate metrics (will try IBKR -> FMP -> yfinance)
metrics = analyzer.calculate_metrics() 

# Access key metrics
gamma_profile = metrics['gamma_profile']
high_gamma_strikes = metrics['high_gamma_strikes']
gex = metrics['gex']
vwiv = metrics['vwiv']
total_open_interest = metrics['total_open_interest'] 
data_source = metrics.get('source', 'Unknown') # Check where data came from
```

### Available Metrics

- **Gamma Profile**: Distribution of gamma across all strikes
- **High Gamma Strikes**: Strikes with the highest gamma concentration
- **Gamma Exposure (GEX)**: Market maker hedging pressure
- **Volume-Weighted Implied Volatility (VWIV)**: Volatility weighted by trading volume
- **Total Open Interest**: Sum of open interest across calls and puts for the expiration
- **Charm**: Delta decay over time
- **Vanna**: Delta sensitivity to volatility changes
- **Vomma**: Vega sensitivity to volatility changes

## Social Media Sentiment Analysis

The `SentimentAnalyzer` module fetches data from configured sources (Twitter via `tweepy`, Reddit via `praw`, StockTwits via direct API call using `requests`) and calculates sentiment using the VADER library:
- **Overall Sentiment Score**: Average compound score across enabled sources (-1 to 1, normalized to 0-1 for filtering).
- **Source-Specific Scores**: Individual compound scores for each platform.
- **Sentiment Trend**: Calculated based on historical scores ('improving', 'declining', 'stable').

```python
from src.modules.sentiment_analysis import SentimentAnalyzer

analyzer = SentimentAnalyzer('TSLA')
sentiment = analyzer.analyze_sentiment()

overall_score = sentiment['overall_score'] # Normalized 0-1 score
trend = sentiment['trend']
```
Historical scores are stored daily in `data_cache/sentiment_history/`. Requires appropriate API keys/credentials in `config.json`.

## Alerts System

The `AlertsManager` module allows defining and managing custom alerts based on scan results.
- **Configuration:** Enable alerts and configure notification details (email server, webhook URL) in `config.json`.
- **Management:** Use the "Alerts" tab in the web UI to view, add (using specific fields for common conditions), and delete alert rules. Alert rules are stored in `user_alerts.json`. Conditions are displayed in a readable format.
- **Conditions:** Define alert triggers using UI fields (Symbol, Setup, Confidence) or potentially more complex JSON for less common fields. The system matches against scan result fields (e.g., `symbol`, `setup`, `min_confidence`, `market_context.rsi_max`).
- **Notifications:** Triggered alerts can use configured methods ("browser", "email", "webhook"). Email and webhook sending logic is implemented but requires correct configuration in `config.json`. Browser notifications are implemented via SSE.
- **History:** View a history of triggered alerts in the "Alerts" tab (stored in `alert_history.json`).

## Project Structure

```
options-technical-hybrid-scanner/
├── src/
│   ├── modules/           # Core modules
│   │   ├── market_context.py
│   │   ├── key_levels.py
│   │   ├── trade_setup.py
│   │   ├── confirmation.py
│   │   ├── risk_management.py
│   │   ├── scanner.py
│   │   ├── options_metrics.py
│   │   ├── sentiment_analysis.py
│   │   └── alerts.py
│   ├── utils/             # Utility functions
│   │   └── data_cache.py
│   └── web/               # Web interface
│       ├── __init__.py
│       └── app.py
├── static/
│   ├── css/               # Stylesheets
│   ├── js/                # JavaScript files
│   └── images/            # Images
├── templates/             # HTML templates
│   └── index.html
├── data_cache/            # Default cache directory
│   └── sentiment_history/ # Historical sentiment data
├── requirements.txt       # Dependencies
├── config.json            # Configuration (API keys, settings)
├── user_alerts.json       # User-defined alerts (managed via UI)
├── alert_history.json     # History of triggered alerts
├── test_options_metrics.py # Test script
└── README.md              # Documentation
```

## Development Phases

### Phase 1: Core Functionality (Completed)
- Market context analysis with EMAs, RSI, Stochastic RSI
- Options data integration (OI, volume, PCR, VWIV)
- Key levels mapping (support/resistance, max pain, high gamma)
- Trade setup engine (bullish/bearish/neutral with confidence scoring)
- Risk management (position sizing, stop-loss calculation)
- Scanner with configurable filters and results storage

### Phase 2: Advanced Features (Completed)
- ✅ Add advanced options metrics (gamma, charm, vanna, vomma, VWIV, GEX, Total OI)
- ✅ Integrate options metrics into scanner filtering (Gamma, GEX, Volume, OI)
- ✅ Implement social media sentiment analysis (API calls, scoring, historical storage, trend calculation)
- ✅ Integrate multiple options data sources (IBKR > FMP > yfinance)
- ✅ Integrate sentiment filters into scanner UI and logic
- ✅ Implement alerts system (condition matching, email/webhook logic, UI management, browser notifications, history tracking)

### Phase 3: User Experience and Optimization (In Progress)
- ✅ Improve EMA chart visualization with historical data.
- ✅ Optimize scan performance using concurrent processing.
- ✅ Improve Key Levels chart visualization using scatter plot.
- ✅ Add GEX Profile chart visualization.
- ✅ Improve Risk/Reward chart visualization using scatter plot.
- ✅ Add sparkline charts to dashboard setup lists.
- ✅ Add zoom/pan functionality to analysis charts.
- ✅ Add sorting to dashboard results table.
- ✅ Add numerical display for key options metrics (GEX, VWIV, Max Pain).
- ✅ Add filtering to dashboard results table via setup lists.
- ✅ Improve display format for alert conditions in UI.
- ✅ Refine sentiment analysis scoring using VADER.
- ✅ Improve UI for adding alert conditions (using specific fields).
- ⏳ Improve UI with more interactive visualizations and dashboards.
- ⏳ Launch educational resources (tutorials, guides, webinars).

## License

MIT
