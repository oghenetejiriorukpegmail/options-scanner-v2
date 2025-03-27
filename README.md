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
- **Scanner Feature**: Filter stocks and deliver actionable insights
- **Advanced Options Metrics**: Analyze gamma, charm, vanna, vomma, VWIV, and GEX
- **Social Media Sentiment Analysis**: Incorporate sentiment from Twitter, Reddit, and StockTwits

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/options-technical-hybrid-scanner.git
cd options-technical-hybrid-scanner
python -m venv .venv
.venv\Scripts\activate.ps1

# Install dependencies
pip install -r requirements.txt

# Create cache directory
mkdir data_cache
```

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
   - Options chains
   - Implied volatility
   - Open interest
   - Greeks (delta, gamma, vega, theta)
   - Advanced metrics (charm, vanna, vomma)

3. **Technical Indicators**:
   - EMA/RSI calculations
   - Support/resistance levels
   - Volume profiles

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
- To clear cache: Delete the `data_cache` folder
- Cache files are automatically pruned after 7 days
- Debug logs show cache hits/misses
```

## Usage

```bash
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

The scanner now includes advanced options metrics analysis through the `OptionsMetricsAnalyzer` module:

```python
from src.modules.options_metrics import OptionsMetricsAnalyzer

# Initialize analyzer
analyzer = OptionsMetricsAnalyzer('TSLA')

# Calculate metrics
metrics = analyzer.calculate_metrics()

# Access key metrics
gamma_profile = metrics['gamma_profile']
high_gamma_strikes = metrics['high_gamma_strikes']
gex = metrics['gex']
vwiv = metrics['vwiv']
```

### Available Metrics

- **Gamma Profile**: Distribution of gamma across all strikes
- **High Gamma Strikes**: Strikes with the highest gamma concentration
- **Gamma Exposure (GEX)**: Market maker hedging pressure
- **Volume-Weighted Implied Volatility (VWIV)**: Volatility weighted by trading volume
- **Charm**: Delta decay over time
- **Vanna**: Delta sensitivity to volatility changes
- **Vomma**: Vega sensitivity to volatility changes

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
│   │   └── sentiment_analysis.py
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
├── requirements.txt       # Dependencies
├── config.json            # Configuration
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

### Phase 2: Advanced Features (In Progress)
- ✅ Add advanced options metrics (gamma, charm, vanna, vomma, VWIV, GEX)
- ⏳ Integrate social media sentiment analysis
- ⏳ Enhance the scanner with sophisticated filters and real-time alerts

### Phase 3: User Experience and Optimization (Planned)
- Improve UI with interactive visualizations and dashboards
- Optimize performance for real-time data handling
- Launch educational resources (tutorials, guides, webinars)

## License

MIT
