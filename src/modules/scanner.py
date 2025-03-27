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
                
                # Map key levels
                levels = key_levels.map_levels()
                
                # Determine trade setup
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
                
            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {e}")
                return None
                
            # Build result dictionary
            result = {
                'symbol': symbol,
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
        
        # Filter by trend
        if result['market_context']['trend'] not in filters['trend']:
            return False
        
        # Filter by PCR
        if not (filters['pcr_min'] <= result['market_context']['pcr'] <= filters['pcr_max']):
            return False
        
        # Filter by RSI
        if not (filters['rsi_min'] <= result['market_context']['rsi'] <= filters['rsi_max']):
            return False
        
        # Filter by Stochastic RSI
        if not (filters['stoch_rsi_min'] <= result['market_context']['stoch_rsi'] <= filters['stoch_rsi_max']):
            return False
        
        # Filter by confidence
        if result['confidence'] < filters['min_confidence']:
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
        logger.info(f"Starting scan for {len(self.symbols)} symbols")
        print(f"Starting scan for {len(self.symbols)} symbols")

        self.results = []
        total_symbols = len(self.symbols)
        batch_size = 50  # Process symbols in batches to avoid rate limits
        request_delay = 0.5  # Delay between API calls in seconds
        
        # Initialize progress tracking
        if self.progress_callback:
            self.progress_callback({
                'progress': 0,
                'message': 'Starting scan...',
                'current_symbol': None
            })

        try:
            # Process symbols in batches
            for batch_start in range(0, total_symbols, batch_size):
                batch_end = min(batch_start + batch_size, total_symbols)
                batch_symbols = self.symbols[batch_start:batch_end]
                
                for i, symbol in enumerate(batch_symbols):
                    # Calculate overall progress
                    overall_i = batch_start + i
                    progress = int(((overall_i + 1) / total_symbols) * 100)
                    message = f'Processing {symbol}... ({overall_i+1}/{total_symbols})'
                    logger.info(message)
                    print(message)
                    
                    # Update progress through callback
                    if self.progress_callback:
                        self.progress_callback({
                            'progress': progress,
                            'message': message,
                            'current_symbol': symbol
                        })
                    
                    try:
                        # Get price data with timeout
                        ticker = yf.Ticker(symbol)
                        hist = ticker.history(period='1d', timeout=10)
                        if hist.empty:
                            logger.error(f"No price data available for {symbol}")
                            continue
                            
                        current_price = hist['Close'].iloc[-1]
                        logger.info(f"Fetched price for {symbol}: ${current_price:.2f}")
                        
                        # Initialize modules
                        context_analyzer = MarketContextAnalyzer(symbol)
                        levels_mapper = KeyLevelsMapper(symbol)
                        setup_engine = TradeSetupEngine(symbol)
                        risk_manager = RiskManager(account_size=100000)  # Default $100k account
                        
                        # Get market context
                        context = context_analyzer.analyze()
                        if not context.get('success', False):
                            continue
                            
                        # Get key levels
                        levels = levels_mapper.map_levels()
                        if not levels.get('success', False):
                            continue
                            
                        # Determine trade setup
                        setup = setup_engine.determine_setup(context, levels)
                        
                        # Calculate risk parameters
                        stop_loss = risk_manager.calculate_stop_loss(
                            setup['setup'],
                            levels['current_price'],
                            support_resistance=levels
                        )
                        
                        position_size = risk_manager.calculate_position_size(
                            levels['current_price'],
                            stop_loss
                        )
                        
                        # Calculate target price (1.5x risk-reward ratio)
                        risk_amount = abs(levels['current_price'] - stop_loss)
                        target_price = levels['current_price'] + (risk_amount * 1.5 * (1 if setup['setup'] == 'bullish' else -1))
                        
                        # Format results
                        result = {
                            'symbol': symbol,
                            'timestamp': datetime.now().isoformat(),
                            'setup': setup['setup'],
                            'confidence': setup['confidence'],
                            'reasons': setup['reasons'],
                            'entry_signal': True,  # All filtered setups are valid entries
                            'entry_strength': setup['confidence'],
                            'entry_reasons': setup['reasons'],
                            'exit_signal': False,  # Exit signals handled separately
                            'exit_strength': 0,
                            'exit_reasons': [],
                            'position_size': position_size,
                            'stop_loss': stop_loss,
                            'risk_reward': 1.5,
                            'target_price': target_price,
                            'current_price': levels['current_price'],
                            'market_context': context,
                            'key_levels': levels
                        }
                        
                        # Apply filters before adding to results
                        if self._apply_filters(result):
                            self.results.append(result)
                            logger.info(f"Added {symbol} to results")
                        else:
                            logger.info(f"Filtered out {symbol} setup: confidence={setup['confidence']:.1f}%, trend={setup['setup']}")
                    except Exception as e:
                        logger.error(f"Error analyzing {symbol}: {e}")
                        continue
            
            # Log pre-filter results count
            logger.info(f"Pre-filter results count: {len(self.results)}")
            
            # Apply filters and log which results are filtered out
            filtered_results = []
            for r in self.results:
                if self._apply_filters(r):
                    filtered_results.append(r)
                else:
                    logger.info(f"Filtered out {r['symbol']} setup: confidence={r['confidence']:.1f}%, trend={r['market_context']['trend']}")
            
            # Sort filtered results by confidence
            filtered_results.sort(key=lambda x: x['confidence'], reverse=True)
            
            # Update self.results with filtered results
            self.results = filtered_results
            
            # Log post-filter results count
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