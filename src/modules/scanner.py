"""
Scanner Module

This module filters stocks and delivers actionable insights.
"""

import logging
import json
import os
import time
import random
import pandas as pd
import yfinance as yf
import requests
import concurrent.futures
import threading
from datetime import datetime
from tqdm import tqdm

from src.modules.market_context import MarketContextAnalyzer
from src.modules.key_levels import KeyLevelsMapper
from src.modules.trade_setup import TradeSetupEngine
from src.modules.confirmation import ConfirmationModule
from src.modules.risk_management import RiskManager
from src.modules.options_metrics import OptionsMetricsAnalyzer # Added import
from src.modules.alerts import AlertsManager # Added import

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scanner.log')
    ]
)
logger = logging.getLogger(__name__)

class StockScanner:
    """
    Filters stocks and delivers actionable insights
    
    Features:
    - Custom Filters
    - Real-Time Alerts
    - Visualizations
    """
    
    def __init__(self, config_file=None, progress_callback=None):
        """
        Initialize the Stock Scanner
        
        Args:
            config_file (str, optional): Path to configuration file
            progress_callback (callable, optional): Callback function to report progress
        """
        if config_file is None:
            config_file = 'config.json'  # Default to config.json in the root directory
        
        self.config = self._load_config(config_file)
        self.symbols = self._load_symbols()
        self.results = []
        self.progress_callback = progress_callback
        self.alerts_manager = AlertsManager(config=self.config) # Instantiate AlertsManager
    
    def _load_config(self, config_file):
        """Load scanner configuration"""
        default_config = {
            'max_workers': 5,
            'filters': {
                'trend': ['bullish', 'bearish', 'neutral'],
                'pcr_min': 0,
                'pcr_max': 2,
                'rsi_min': 0,
                'rsi_max': 100,
                'stoch_rsi_min': 0,
                'stoch_rsi_max': 100,
                'min_confidence': 60
            },
            'output_dir': 'scanner_results'
        }
        
        try:
            if os.path.exists(config_file):
                logger.info(f"Loading configuration from {config_file}")
                with open(config_file, 'r') as f:
                    user_config = json.load(f)
                    # Merge user config with default config
                    for key, value in user_config.items():
                        if key in default_config and isinstance(value, dict) and isinstance(default_config[key], dict):
                            default_config[key].update(value)
                        else:
                            default_config[key] = value
            else:
                logger.warning(f"Config file {config_file} not found, using default configuration")
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
        
        return default_config
    
    def _fetch_nasdaq_constituents(self):
        """Fetch current NASDAQ Composite constituents from FMP API"""
        from src.utils.data_cache import DataCache
        cache = DataCache(max_fresh_fetches=3)
        cache_key = 'nasdaq_constituents'
        
        # Check if we should use cached data
        if not cache.should_fetch(cache_key):
            cached_data = cache.get_cache(cache_key)
            if cached_data:
                logger.info("Using cached NASDAQ constituents")
                return cached_data['symbols']
        
        # Fetch from API
        try:
            if 'fmp_api_key' not in self.config:
                raise ValueError("FMP API key not configured")
                
            url = f"https://financialmodelingprep.com/api/v3/nasdaq_constituent?apikey={self.config['fmp_api_key']}"
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if not isinstance(data, list):
                raise ValueError("Unexpected API response format")
                
            symbols = [item['symbol'] for item in data if 'symbol' in item]
            
            # Update cache using DataCache
            from src.utils.data_cache import DataCache
            cache = DataCache()
            cache.set_cache('nasdaq_constituents', {
                'timestamp': time.time(),
                'symbols': symbols
            })
                
            return symbols
            
        except Exception as e:
            logger.error(f"Error fetching NASDAQ constituents: {e}")
            # Try to return from cache even if expired
            cached_data = self.cache.get_cache(cache_key)
            if cached_data:
                return cached_data['symbols']
            raise

    def _load_symbols(self):
        """Load stock symbols to scan"""
        try:
            # First try to get from API
            symbols = self._fetch_nasdaq_constituents()
            logger.info(f"Loaded {len(symbols)} symbols from NASDAQ Composite")
            return symbols
        except Exception as e:
            logger.error(f"Failed to load NASDAQ constituents: {e}")
            
            # Fallback to config symbols if available
            if 'symbols' in self.config and self.config['symbols']:
                logger.info("Using symbols from config")
                return self.config['symbols']
                
            # Final fallback to hardcoded symbols
            logger.warning("Using hardcoded fallback symbols")
            return ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA']
    
    def _analyze_symbol(self, symbol):
        """
        Analyze a single symbol
        
        Args:
            symbol (str): Stock symbol to analyze
            
        Returns:
            dict: Analysis results
        """
        logger.info(f"Analyzing {symbol}")
        
        try:
            try:
                # Initialize analysis modules
                market_analyzer = MarketContextAnalyzer(symbol)
                if not market_analyzer._fetch_data():
                    logger.error(f"Failed to fetch data for {symbol}")
                    return None
                
                # Validate we have sufficient price data
                if len(market_analyzer.data) < 20:  # Need at least 20 days for indicators
                    logger.error(f"Insufficient data for {symbol} - only {len(market_analyzer.data)} days available")
                    return None
                
                current_price = market_analyzer.data['Close'].iloc[-1]
                
                # Calculate actual indicators and get market context
                market_analyzer._calculate_indicators()
                market_context = market_analyzer.analyze()
                if not market_context.get('success', False):
                    logger.error(f"Failed to analyze market context for {symbol}")
                    return None

                # Initialize analysis modules
                key_levels = KeyLevelsMapper(symbol)
                trade_setup = TradeSetupEngine(symbol)
                risk_manager = RiskManager(100000)  # Default $100k account
                options_metrics_analyzer = OptionsMetricsAnalyzer(symbol) # Added instantiation
                
                # Map key levels
                levels = key_levels.map_levels()
                
                # Determine trade setup
                logger.info(f"Calling determine_setup with context: {market_context is not None} and levels: {levels is not None}")
                setup = trade_setup.determine_setup(market_context, levels)
                
                # Ensure we're working with scalar values for price
                current_price = float(levels['current_price']) if isinstance(levels['current_price'], (int, float)) else levels['current_price'][0]
                
                # Calculate stop loss
                try:
                    stop_loss = risk_manager.calculate_stop_loss(
                        setup['setup'],
                        current_price,
                        support_resistance=levels
                    )
                except Exception as e:
                    # Fallback to a simple percentage-based stop loss if there's an error
                    logger.warning(f"Error calculating stop loss for {symbol}: {e}")
                    if setup['setup'] == 'bullish':
                        stop_loss = current_price * 0.95  # 5% below current price
                    else:
                        stop_loss = current_price * 1.05  # 5% above current price
                
                # Ensure stop_loss is a scalar value
                stop_loss_value = float(stop_loss) if isinstance(stop_loss, (int, float)) else stop_loss[0]
                
                # Calculate position size
                position_size = risk_manager.calculate_position_size(
                    current_price,
                    stop_loss_value
                )
                
                # Calculate risk parameters
                risk_amount = abs(current_price - stop_loss_value)
                direction = 1 if setup['setup'] == 'bullish' else -1
                target_price = current_price + (risk_amount * 1.5 * direction)
                
                logger.info(f"Current price: {current_price}, Stop loss: {stop_loss_value}")
                logger.info(f"Risk amount: {risk_amount}, Direction: {direction}, Target price: {target_price}")
                
                risk_params = {
                    'position_size': position_size,
                    'stop_loss': stop_loss_value,
                    'risk_reward': 1.5,  # Default risk-reward ratio
                    'target_price': target_price
                }

                # Calculate options metrics
                options_metrics = options_metrics_analyzer.calculate_metrics()
                if options_metrics is None:
                    logger.warning(f"Could not calculate options metrics for {symbol}")
                    options_metrics = {} # Use empty dict if calculation fails
                
            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {e}")
                return None
                
            # Extract historical data for charting
            historical_df = market_analyzer.data.tail(60) # Get last 60 days
            historical_chart_data = {
                 'dates': [d.strftime('%Y-%m-%d') for d in historical_df.index],
                 'price': historical_df['Close'].tolist(),
                 'ema10': historical_df['ema10'].tolist(),
                 'ema20': historical_df['ema20'].tolist(),
                 'ema50': historical_df['ema50'].tolist(),
            }
            # Extract sparkline data (last 15 closing prices)
            sparkline_data = market_analyzer.data['Close'].tail(15).tolist()

            # Build result dictionary
            result = {
                'symbol': symbol,
                'sparkline_data': sparkline_data, # Added sparkline data
                'options_metrics': options_metrics, # Added options metrics
                'historical_chart_data': historical_chart_data, # Added historical data
                'timestamp': datetime.now().isoformat(),
                'setup': setup['setup'],
                'confidence': setup['confidence'],
                'reasons': setup['reasons'],
                'entry_signal': True,  # Default to true for valid setups
                'entry_strength': setup['confidence'],
                'entry_reasons': setup['reasons'],
                'exit_signal': False,  # Default to false
                'exit_strength': 0,
                'exit_reasons': [],
                'position_size': risk_params['position_size']['risk_percent'] / 100,  # Convert to percentage of account
                'stop_loss': risk_params['stop_loss'],
                'risk_reward': risk_params['risk_reward'],
                'target_price': risk_params['target_price'],
                'current_price': current_price,
                'market_context': market_context,
                'key_levels': levels
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return None
    
    def _apply_filters(self, result):
        """
        Apply filters to scan results

        Args:
            result (dict): Analysis result

        Returns:
            bool: True if result passes filters, False otherwise
        """
        filters = self.config['filters']
        symbol = result.get('symbol', 'UNKNOWN') # Get symbol for logging

        # If min_confidence is explicitly set to 0, bypass all other filters
        # This ensures all symbols are returned when requested.
        min_confidence_filter = filters.get('min_confidence', 60) # Default to 60 if not set
        if isinstance(min_confidence_filter, (int, float)) and min_confidence_filter == 0:
             # Check only confidence against the 0 threshold (which will always pass if confidence is not None)
             confidence = result.get('confidence')
             if confidence is None or not isinstance(confidence, (int, float)):
                 logger.info(f"Filtering {symbol}: Confidence is missing or not a number ('{confidence}')")
                 return False
             # If confidence is valid and min_confidence is 0, it passes
             return True

        # --- Original Filter Logic ---

        # Filter by trend
        trend = result.get('market_context', {}).get('trend')
        allowed_trends = filters.get('trend', [])
        if trend not in allowed_trends:
            logger.info(f"Filtering {symbol}: Trend '{trend}' not in allowed trends {allowed_trends}")
            return False

        # Filter by PCR
        pcr = result.get('market_context', {}).get('pcr')
        pcr_min = filters.get('pcr_min', 0)
        pcr_max = filters.get('pcr_max', 2)
        if pcr is None or not isinstance(pcr, (int, float)) or not (pcr_min <= pcr <= pcr_max):
             logger.info(f"Filtering {symbol}: PCR '{pcr}' outside range [{pcr_min}, {pcr_max}]")
             return False

        # Filter by RSI
        rsi = result.get('market_context', {}).get('rsi')
        rsi_min = filters.get('rsi_min', 0)
        rsi_max = filters.get('rsi_max', 100)
        if rsi is None or not isinstance(rsi, (int, float)) or not (rsi_min <= rsi <= rsi_max):
             logger.info(f"Filtering {symbol}: RSI '{rsi}' outside range [{rsi_min}, {rsi_max}]")
             return False

        # Filter by Stochastic RSI
        stoch_rsi = result.get('market_context', {}).get('stoch_rsi')
        stoch_rsi_min = filters.get('stoch_rsi_min', 0)
        stoch_rsi_max = filters.get('stoch_rsi_max', 100)
        # Add a small epsilon to the max check for floating point precision
        epsilon = 1e-9
        if stoch_rsi is None or not isinstance(stoch_rsi, (int, float)) or not (stoch_rsi_min <= stoch_rsi <= stoch_rsi_max + epsilon):
             logger.info(f"Filtering {symbol}: Stoch RSI '{stoch_rsi}' outside range [{stoch_rsi_min}, {stoch_rsi_max}]")
             return False

        # Filter by confidence
        confidence = result.get('confidence')
        min_confidence = filters.get('min_confidence', 60) # Default to 60 if not set (Changed default from 0)
        if confidence is None or not isinstance(confidence, (int, float)) or confidence < min_confidence:
             logger.info(f"Filtering {symbol}: Confidence '{confidence}' below minimum {min_confidence}")
             return False

        # --- Advanced Options Metrics Filters ---
        options_metrics = result.get('options_metrics', {})

        # Filter by Gamma (using max gamma from profile)
        gamma_min_filter = filters.get('gamma_min')
        if gamma_min_filter is not None:
            gamma_profile = options_metrics.get('gamma_profile', [])
            if not gamma_profile:
                 logger.info(f"Filtering {symbol}: No gamma profile available for gamma_min filter")
                 return False
            max_gamma = max(item.get('total_gamma', 0) for item in gamma_profile) if gamma_profile else 0
            if max_gamma < gamma_min_filter:
                 logger.info(f"Filtering {symbol}: Max Gamma '{max_gamma:.4f}' below minimum {gamma_min_filter}")
                 return False

        # Filter by GEX Direction
        gex_direction_filter = filters.get('gex_direction')
        if gex_direction_filter is not None:
            gex_data = options_metrics.get('gex', {})
            actual_gex_direction = gex_data.get('gex_direction')
            if actual_gex_direction is None or actual_gex_direction != gex_direction_filter:
                 logger.info(f"Filtering {symbol}: GEX Direction '{actual_gex_direction}' does not match filter '{gex_direction_filter}'")
                 return False

        # Filter by VWIV Percentile (Placeholder - requires percentile calculation)
        # vwiv_percentile_min_filter = filters.get('vwiv_percentile_min')
        # if vwiv_percentile_min_filter is not None:
        #     vwiv_percentile = options_metrics.get('vwiv_percentile') # Assuming this key exists
        #     if vwiv_percentile is None or vwiv_percentile < vwiv_percentile_min_filter:
        #         logger.info(f"Filtering {symbol}: VWIV Percentile '{vwiv_percentile}' below minimum {vwiv_percentile_min_filter}")
        #         return False

        # Filter by Minimum Option Volume
        min_option_volume_filter = filters.get('min_option_volume')
        if min_option_volume_filter is not None:
            # Using total_volume calculated in calculate_vwiv
            vwiv_data = options_metrics.get('vwiv', {})
            total_volume = vwiv_data.get('total_volume')
            if total_volume is None or total_volume < min_option_volume_filter:
                 logger.info(f"Filtering {symbol}: Total Option Volume '{total_volume}' below minimum {min_option_volume_filter}")
                 return False

        # Filter by Minimum Open Interest (Placeholder - requires total OI calculation)
        min_open_interest_filter = filters.get('min_open_interest')
        if min_open_interest_filter is not None:
            total_open_interest = options_metrics.get('total_open_interest') # Assuming this key exists
            if total_open_interest is None or total_open_interest < min_open_interest_filter:
                 logger.info(f"Filtering {symbol}: Total Open Interest '{total_open_interest}' below minimum {min_open_interest_filter}")
                 return False

        # --- Sentiment Filters ---
        sentiment_min_filter = filters.get('sentiment_min')
        if sentiment_min_filter is not None:
            # Use 'social_sentiment' key added in market_context.py
            social_sentiment = result.get('market_context', {}).get('social_sentiment')
            # Check if sentiment score is valid (not None) before comparing
            if social_sentiment is None or not isinstance(social_sentiment, (int, float)) or social_sentiment < sentiment_min_filter:
                logger.info(f"Filtering {symbol}: Social Sentiment '{social_sentiment}' below minimum {sentiment_min_filter} or invalid.")
                return False
        
        sentiment_trend_filter = filters.get('sentiment_trend')
        # Ensure the filter is a list and not empty
        if isinstance(sentiment_trend_filter, list) and sentiment_trend_filter:
            # Use 'sentiment_trend' key added in market_context.py
            sentiment_trend = result.get('market_context', {}).get('sentiment_trend')
            if sentiment_trend is None or sentiment_trend not in sentiment_trend_filter:
                logger.info(f"Filtering {symbol}: Sentiment Trend '{sentiment_trend}' not in allowed trends {sentiment_trend_filter}")
                return False

        return True
    
    def _save_results(self):
        """Save scan results to file"""
        if not self.results:
            logger.warning("No results to save")
            return
        
        # Create output directory if it doesn't exist
        output_dir = self.config['output_dir']
        os.makedirs(output_dir, exist_ok=True)
        
        # Save results to JSON file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(output_dir, f"scan_results_{timestamp}.json")
        
        try:
            with open(output_file, 'w') as f:
                json.dump(self.results, f, indent=2)
            logger.info(f"Results saved to {output_file}")
        except Exception as e:
            logger.error(f"Error saving results: {e}")
    
    def scan(self):
        """
        Scan stocks for trading opportunities and report progress through callback
        
        Returns:
            list: Scan results
        """
        logger.info(f"Starting concurrent scan for {len(self.symbols)} symbols")
        print(f"Starting concurrent scan for {len(self.symbols)} symbols")

        self.results = [] # Reset results
        total_symbols = len(self.symbols)
        # Use max_workers from config for thread pool size
        max_workers = self.config.get('max_workers', 5)
        completed_count = 0 # Counter for progress

        # Initialize progress tracking
        if self.progress_callback:
            self.progress_callback({
                'progress': 0,
                'message': 'Starting scan...',
                'current_symbol': None
            })

        try:
            # Use ThreadPoolExecutor for concurrent analysis
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit analysis tasks for all symbols
                future_to_symbol = {executor.submit(self._analyze_symbol, symbol): symbol for symbol in self.symbols}
                
                raw_results = [] # Store results before filtering
                
                # Process results as they complete
                for future in concurrent.futures.as_completed(future_to_symbol):
                    symbol = future_to_symbol[future]
                    try:
                        result = future.result()
                        if result:
                            raw_results.append(result)
                            logger.info(f"Analysis complete for {symbol}")
                        else:
                            # _analyze_symbol returns None on failure, error already logged within it
                            pass
                    except Exception as exc:
                        logger.error(f'{symbol} generated an exception during analysis: {exc}')
                    
                    # Update progress
                    completed_count += 1
                    progress = int((completed_count / total_symbols) * 100)
                    message = f'Analyzed {symbol} ({completed_count}/{total_symbols})'
                    print(message) # Keep console print for immediate feedback
                    if self.progress_callback:
                        self.progress_callback({
                            'progress': progress,
                            'message': message,
                            'current_symbol': symbol # Keep track of the last completed symbol
                        })

            # --- Post-Analysis Processing (Filtering, Sorting, Saving) ---
            logger.info(f"Completed analysis for all symbols. Raw results count: {len(raw_results)}")

            # Apply filters to the raw results
            filtered_results = []
            for r in raw_results:
                try:
                    if self._apply_filters(r):
                        filtered_results.append(r)
                    # else: # Logging for filtered out items is now within _apply_filters
                    #    pass
                except Exception as filter_exc:
                     logger.error(f"Error applying filters to result for {r.get('symbol', 'UNKNOWN')}: {filter_exc}")

            # Sort filtered results by confidence
            filtered_results.sort(key=lambda x: x.get('confidence', 0), reverse=True)

            # Update self.results with the final filtered and sorted list
            self.results = filtered_results
            
            logger.info(f"Post-filter results count: {len(self.results)}")
            
            # Save results
            self._save_results()
            
            # Final progress update
            if self.progress_callback:
                self.progress_callback({
                    'progress': 100,
                    'message': f'Scan complete. Found {len(self.results)} setups after filtering.',
                    'current_symbol': None
                })
            
            logger.info(f"Scan complete. Found {len(self.results)} setups after filtering.")
            print(f"Scan complete. Found {len(self.results)} setups after filtering.")

            # Check for alerts based on the final results
            try:
                self.alerts_manager.check_alerts(self.results)
            except Exception as alert_e:
                logger.error(f"Error during alert checking: {alert_e}")

            return self.results
            
        except Exception as e:
            error_msg = f"Scan failed: {str(e)}"
            logger.error(error_msg)
            print(error_msg)
            if self.progress_callback:
                self.progress_callback({
                    'progress': 0,
                    'message': 'Scan failed',
                    'error': error_msg
                })
            raise
    
    def get_bullish_setups(self):
        """Get bullish setups"""
        return [r for r in self.results if r['setup'].startswith('bullish')]
    
    def get_bearish_setups(self):
        """Get bearish setups"""
        return [r for r in self.results if r['setup'].startswith('bearish')]
    
    def get_neutral_setups(self):
        """Get neutral setups"""
        return [r for r in self.results if r['setup'].startswith('neutral')]
    
    def get_entry_signals(self):
        """Get setups with entry signals"""
        return [r for r in self.results if r['entry_signal']]