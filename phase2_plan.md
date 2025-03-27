# Options-Technical Hybrid Scanner: Phase 2 Implementation Plan

## Overview

Phase 2 will build upon the core functionality established in Phase 1 by adding advanced options metrics, social media sentiment analysis, and enhanced scanner capabilities with sophisticated filters and real-time alerts.

## 1. Advanced Options Metrics Implementation

### 1.1 New Options Metrics Module

Create a new module `src/modules/options_metrics.py` to calculate and analyze advanced options metrics:

```python
class OptionsMetricsAnalyzer:
    """
    Analyzes advanced options metrics including:
    - Gamma
    - Charm
    - Vanna
    - Vomma
    - Volume-Weighted Implied Volatility (VWIV)
    - Gamma Exposure (GEX)
    """
    
    def __init__(self, symbol):
        self.symbol = symbol
        
    def calculate_metrics(self):
        """Calculate all advanced options metrics"""
        # Implementation here
        
    def calculate_gamma(self, options_chain):
        """Calculate gamma for all strikes"""
        # Implementation here
        
    def calculate_charm(self, options_chain):
        """Calculate charm (delta decay) for all strikes"""
        # Implementation here
        
    def calculate_vanna(self, options_chain):
        """Calculate vanna (delta sensitivity to volatility) for all strikes"""
        # Implementation here
        
    def calculate_vomma(self, options_chain):
        """Calculate vomma (vega sensitivity to volatility) for all strikes"""
        # Implementation here
        
    def calculate_vwiv(self, options_chain):
        """Calculate volume-weighted implied volatility"""
        # Implementation here
        
    def calculate_gex(self, options_chain):
        """Calculate gamma exposure across all strikes"""
        # Implementation here
```

### 1.2 Options Data Provider Enhancement

Enhance the data provider to fetch options chain data with Greeks:

```python
class OptionsDataProvider:
    """Provides options data with Greeks"""
    
    def __init__(self, cache=None):
        self.cache = cache or DataCache()
        
    def get_options_chain(self, symbol, expiration=None):
        """Get options chain with Greeks for a symbol"""
        # Implementation here
        
    def get_historical_iv(self, symbol, lookback_days=30):
        """Get historical implied volatility data"""
        # Implementation here
```

### 1.3 Integration with Key Levels Module

Update the `KeyLevelsMapper` class to incorporate gamma-related levels:

```python
def map_levels(self):
    # Existing code
    
    # Add gamma-related levels
    options_metrics = OptionsMetricsAnalyzer(self.symbol)
    metrics = options_metrics.calculate_metrics()
    
    # Add high gamma levels
    levels['high_gamma'] = metrics['high_gamma_strikes']
    
    # Add GEX inflection points
    levels['gex_inflection'] = metrics['gex_inflection_points']
    
    return levels
```

### 1.4 UI Updates for Options Metrics

Update the web interface to display advanced options metrics:

- Add a new "Options Metrics" section to the analysis page
- Create visualizations for gamma distribution, GEX profile, and VWIV term structure
- Add tooltips explaining each metric

## 2. Social Media Sentiment Analysis

### 2.1 Sentiment Analysis Module

Create a new module `src/modules/sentiment_analysis.py`:

```python
class SentimentAnalyzer:
    """
    Analyzes social media sentiment for stocks
    
    Sources:
    - Twitter/X
    - Reddit (r/wallstreetbets, r/options, etc.)
    - StockTwits
    """
    
    def __init__(self, symbol, cache=None):
        self.symbol = symbol
        self.cache = cache or DataCache()
        
    def analyze_sentiment(self):
        """Analyze overall sentiment across platforms"""
        # Implementation here
        
    def get_twitter_sentiment(self):
        """Get sentiment from Twitter/X"""
        # Implementation here
        
    def get_reddit_sentiment(self):
        """Get sentiment from Reddit"""
        # Implementation here
        
    def get_stocktwits_sentiment(self):
        """Get sentiment from StockTwits"""
        # Implementation here
        
    def get_sentiment_trends(self, days=7):
        """Get sentiment trends over time"""
        # Implementation here
```

### 2.2 API Integration for Social Media

Add API integrations for social media platforms:

```python
class TwitterAPI:
    """Twitter/X API client"""
    # Implementation here
    
class RedditAPI:
    """Reddit API client"""
    # Implementation here
    
class StocktwitsAPI:
    """StockTwits API client"""
    # Implementation here
```

### 2.3 Integration with Market Context

Update the `MarketContextAnalyzer` to incorporate sentiment data:

```python
def analyze(self):
    # Existing code
    
    # Add sentiment analysis
    sentiment_analyzer = SentimentAnalyzer(self.symbol)
    sentiment_data = sentiment_analyzer.analyze_sentiment()
    
    context['social_sentiment'] = sentiment_data['overall_score']
    context['sentiment_breakdown'] = {
        'twitter': sentiment_data['twitter_score'],
        'reddit': sentiment_data['reddit_score'],
        'stocktwits': sentiment_data['stocktwits_score']
    }
    context['sentiment_trend'] = sentiment_data['trend']
    
    return context
```

### 2.4 UI Updates for Sentiment Analysis

Update the web interface to display sentiment data:

- Add a "Social Sentiment" section to the analysis page
- Create visualizations for sentiment trends
- Add sentiment indicators to the dashboard

## 3. Enhanced Scanner with Sophisticated Filters

### 3.1 Advanced Filtering System

Enhance the `StockScanner` class with advanced filtering capabilities:

```python
def _apply_filters(self, result):
    """Apply advanced filters to scan results"""
    filters = self.config['filters']
    
    # Existing filters
    
    # Advanced options metrics filters
    if 'gamma_min' in filters and result['options_metrics']['gamma'] < filters['gamma_min']:
        return False
        
    if 'gex_direction' in filters and result['options_metrics']['gex_direction'] != filters['gex_direction']:
        return False
        
    if 'vwiv_percentile_min' in filters and result['options_metrics']['vwiv_percentile'] < filters['vwiv_percentile_min']:
        return False
    
    # Sentiment filters
    if 'sentiment_min' in filters and result['market_context']['social_sentiment'] < filters['sentiment_min']:
        return False
        
    if 'sentiment_trend' in filters and result['market_context']['sentiment_trend'] not in filters['sentiment_trend']:
        return False
    
    # Volume and liquidity filters
    if 'min_option_volume' in filters and result['options_metrics']['total_volume'] < filters['min_option_volume']:
        return False
        
    if 'min_open_interest' in filters and result['options_metrics']['total_open_interest'] < filters['min_open_interest']:
        return False
    
    return True
```

### 3.2 Real-Time Alerts System

Create a new module `src/modules/alerts.py`:

```python
class AlertsManager:
    """
    Manages real-time alerts for trading setups
    
    Features:
    - Custom alert conditions
    - Multiple notification methods
    - Alert history tracking
    """
    
    def __init__(self, config=None):
        self.config = config or {}
        self.alerts = []
        
    def check_alerts(self, scan_results):
        """Check scan results against alert conditions"""
        # Implementation here
        
    def create_alert(self, alert_type, conditions, notification_methods):
        """Create a new alert"""
        # Implementation here
        
    def send_notification(self, alert, result):
        """Send notification for triggered alert"""
        # Implementation here
        
    def get_alert_history(self):
        """Get history of triggered alerts"""
        # Implementation here
```

### 3.3 Notification Methods

Implement multiple notification methods:

```python
class EmailNotifier:
    """Email notification sender"""
    # Implementation here
    
class WebhookNotifier:
    """Webhook notification sender"""
    # Implementation here
    
class BrowserNotifier:
    """Browser notification sender"""
    # Implementation here
```

### 3.4 UI Updates for Advanced Filtering and Alerts

Update the web interface for advanced filtering and alerts:

- Add advanced filter options to the scanner configuration
- Create an alerts management interface
- Implement real-time browser notifications
- Add alert history view

## 4. Configuration Updates

Update `config.json` to include new configuration options:

```json
{
  "max_workers": 5,
  "filters": {
    "trend": ["bullish", "bearish", "neutral"],
    "pcr_min": 0,
    "pcr_max": 2,
    "rsi_min": 0,
    "rsi_max": 100,
    "stoch_rsi_min": 0,
    "stoch_rsi_max": 100,
    "min_confidence": 60,
    "gamma_min": 0.1,
    "gex_direction": "positive",
    "vwiv_percentile_min": 50,
    "sentiment_min": 0.6,
    "sentiment_trend": ["improving", "stable"],
    "min_option_volume": 1000,
    "min_open_interest": 500
  },
  "output_dir": "scanner_results",
  "fmp_api_key": "your_fmp_api_key",
  "twitter_api_key": "your_twitter_api_key",
  "reddit_api_key": "your_reddit_api_key",
  "stocktwits_api_key": "your_stocktwits_api_key",
  "alerts": {
    "enabled": true,
    "check_interval": 300,
    "notification_methods": ["browser", "email"],
    "email_settings": {
      "smtp_server": "smtp.example.com",
      "smtp_port": 587,
      "username": "your_email@example.com",
      "password": "your_password",
      "recipients": ["recipient@example.com"]
    }
  }
}
```

## 5. Implementation Timeline

### Week 1-2: Advanced Options Metrics
- Implement `OptionsMetricsAnalyzer` class
- Enhance options data provider
- Integrate with existing modules
- Update UI to display new metrics

### Week 3-4: Social Media Sentiment Analysis
- Implement `SentimentAnalyzer` class
- Set up API integrations
- Integrate with market context
- Update UI to display sentiment data

### Week 5-6: Enhanced Scanner and Alerts
- Implement advanced filtering system
- Create alerts management system
- Implement notification methods
- Update UI for filters and alerts

### Week 7-8: Testing and Optimization
- Comprehensive testing of all new features
- Performance optimization
- Documentation updates
- User acceptance testing

## 6. Dependencies

New dependencies to add to `requirements.txt`:

```
# Options pricing and Greeks
py_vollib==1.0.1
mibian==0.1.0

# API clients
tweepy==4.12.1
praw==7.7.0
stocktwits==0.1.0

# Natural Language Processing
nltk==3.8.1
textblob==0.17.1
vaderSentiment==3.3.2

# Notifications
sendgrid==6.9.7
pywebpush==1.14.0
```

## 7. Testing Strategy

### Unit Tests
- Create tests for each new module
- Test options metrics calculations
- Test sentiment analysis accuracy
- Test alert triggering logic

### Integration Tests
- Test integration between modules
- Test end-to-end scanner workflow
- Test alert notification delivery

### Performance Tests
- Test scanner performance with large symbol lists
- Test real-time alert processing
- Test concurrent API requests

## 8. Documentation Updates

- Update README.md with Phase 2 features
- Create documentation for options metrics
- Create documentation for sentiment analysis
- Create documentation for alerts system
- Update API documentation