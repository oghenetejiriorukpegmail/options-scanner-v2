"""
Options Metrics Module

This module calculates and analyzes advanced options metrics including:
- Gamma
- Charm
- Vanna
- Vomma
- Volume-Weighted Implied Volatility (VWIV)
- Gamma Exposure (GEX)
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import yfinance as yf
import math
import requests
import json
import os
from ib_insync import IB, Stock, Option, util, Contract # Added ib_insync imports

from src.utils.data_cache import DataCache

logger = logging.getLogger(__name__)

class OptionsMetricsAnalyzer:
    """
    Analyzes advanced options metrics for a given symbol
    
    Features:
    - Gamma calculation and analysis
    - Charm (delta decay) calculation
    - Vanna (delta sensitivity to volatility) calculation
    - Vomma (vega sensitivity to volatility) calculation
    - Volume-Weighted Implied Volatility (VWIV) calculation
    - Gamma Exposure (GEX) calculation
    """
    
    def __init__(self, symbol, cache=None):
        """
        Initialize the Options Metrics Analyzer
        
        Args:
            symbol (str): Stock symbol
            cache (DataCache, optional): Cache instance
        """
        self.symbol = symbol.upper()
        self.cache = cache or DataCache()
        self.current_price = None
        self.risk_free_rate = 0.05  # 5% as default, should be updated with current treasury yield
        self.config = self._load_config() # Load config
        self.fmp_api_key = self.config.get('fmp_api_key') # Store FMP key
        self.ibkr_config = self.config.get('ibkr', {}) # Store IBKR config
        
    def _load_config(self, config_file='config.json'):
        """Load necessary configuration"""
        # Load only necessary parts or the whole config
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    return json.load(f)
            else:
                logger.warning(f"Config file {config_file} not found for OptionsMetricsAnalyzer.")
                return {}
        except Exception as e:
            logger.error(f"Error loading config {config_file} in OptionsMetricsAnalyzer: {e}")
            return {}

    def get_current_price(self):
        """Get current price for the symbol"""
        if self.current_price is not None:
            return self.current_price
            
        try:
            ticker = yf.Ticker(self.symbol)
            hist = ticker.history(period='1d')
            if hist.empty:
                logger.error(f"No price data available for {self.symbol}")
                return None
                
            self.current_price = hist['Close'].iloc[-1]
            return self.current_price
        except Exception as e:
            logger.error(f"Error getting price data for {self.symbol}: {e}")
            return None
            
    def get_options_chain(self, expiration=None):
        """
        Get options chain for the symbol
        
        Args:
            expiration (str, optional): Expiration date in YYYY-MM-DD format
            
        Returns:
            dict: Options chain with calls and puts
        """
        cache_key = f"options_chain_{self.symbol}_{expiration or 'nearest'}"
        
        # Check cache first
        if not self.cache.should_fetch(cache_key):
            cached_data = self.cache.get_cache(cache_key)
            if cached_data:
                logger.info(f"Using cached options chain for {self.symbol} (Expiration: {cached_data.get('expiration', 'N/A')}, Source: {cached_data.get('source', 'Unknown')})")
                return cached_data

        # --- Try IBKR First ---
        ib = None # Initialize IB connection variable
        if self.ibkr_config.get('host') and self.ibkr_config.get('port'):
            logger.debug(f"Attempting to fetch options chain for {self.symbol} from IBKR.")
            try:
                # Connect to IBKR TWS/Gateway
                ib = IB()
                ib.connect(
                    self.ibkr_config['host'],
                    self.ibkr_config['port'],
                    clientId=self.ibkr_config.get('client_id', 1),
                    timeout=self.ibkr_config.get('timeout_seconds', 10),
                    readonly=True # Connect in read-only mode
                )
                
                # Qualify the underlying stock contract
                stock_contract = Stock(self.symbol, 'SMART', 'USD') # Adjust exchange/currency if needed
                qualified_contracts = ib.qualifyContracts(stock_contract)
                if not qualified_contracts:
                    raise ValueError(f"Could not qualify stock contract for {self.symbol} on IBKR.")
                underlying_contract = qualified_contracts[0]
                conId = underlying_contract.conId

                # Fetch underlying price (ticker)
                ticker = ib.reqMktData(underlying_contract, '', False, False)
                ib.sleep(1) # Allow time for data to arrive
                if ticker.last is None or np.isnan(ticker.last):
                     # Try fetching historical data as fallback for price
                     bars = ib.reqHistoricalData(underlying_contract, endDateTime='', durationStr='1 D', barSizeSetting='1 day', whatToShow='TRADES', useRTH=True)
                     if bars:
                          current_price = bars[-1].close
                     else:
                          raise ValueError(f"Could not get current price for {self.symbol} from IBKR.")
                else:
                     current_price = ticker.last
                ib.cancelMktData(underlying_contract) # Clean up market data request

                # Fetch options chains
                chains = ib.reqSecDefOptParams(underlying_contract.symbol, '', underlying_contract.secType, conId)
                if not chains:
                     raise ValueError(f"No options chain parameters found for {self.symbol} on IBKR.")
                
                # Find the correct chain (usually only one for SMART exchange)
                # Assuming the first chain is the relevant one, might need adjustment
                chain = chains[0]
                
                # Determine expiration date
                available_expirations = sorted([exp for exp in chain.expirations])
                if not available_expirations:
                     raise ValueError("No expiration dates found from IBKR.")

                if expiration is None:
                    today = datetime.now().date()
                    future_expirations = [exp for exp in available_expirations if datetime.strptime(exp, '%Y%m%d').date() >= today]
                    if not future_expirations:
                         raise ValueError("No future expiration dates found from IBKR.")
                    expiration = future_expirations[0] # Use nearest expiration date string YYYYMMDD
                    logger.info(f"Using nearest IBKR expiration date for {self.symbol}: {expiration}")
                elif expiration.replace('-', '') not in available_expirations: # Convert YYYY-MM-DD to YYYYMMDD if needed
                     raise ValueError(f"Specified expiration {expiration} not found in IBKR available dates: {available_expirations}")
                else:
                     expiration = expiration.replace('-', '') # Ensure YYYYMMDD format

                # Filter strikes around the current price (optional, reduces data volume)
                # Example: +/- 20% around current price
                min_strike = current_price * 0.8
                max_strike = current_price * 1.2
                strikes = [s for s in chain.strikes if min_strike <= s <= max_strike]
                if not strikes:
                     strikes = chain.strikes # Use all strikes if filtering results in none

                # Fetch option contracts for the chosen expiration and strikes
                option_contracts = []
                for right in ['C', 'P']:
                    for strike in strikes:
                        option_contracts.append(Option(self.symbol, expiration, strike, right, 'SMART', tradingClass=underlying_contract.symbol)) # Use symbol as tradingClass
                
                qualified_options = ib.qualifyContracts(*option_contracts)
                if not qualified_options:
                     raise ValueError("Could not qualify any option contracts on IBKR.")

                # Fetch market data (including Greeks) for qualified options
                tickers_data = {}
                for contract in qualified_options:
                    ticker = ib.reqMktData(contract, '100,101,104,106', False, False) # Generic ticks for model Greeks
                    tickers_data[contract.conId] = ticker
                
                ib.sleep(2) # Allow more time for potentially many options tickers

                # Process IBKR data into expected format
                calls = []
                puts = []
                for contract in qualified_options:
                    ticker = tickers_data.get(contract.conId)
                    if not ticker or not ticker.modelGreeks: # Check if modelGreeks data is available
                         logger.debug(f"Missing ticker or modelGreeks for {contract.symbol} {contract.lastTradeDateOrContractMonth} {contract.strike} {contract.right}")
                         continue

                    # Map IBKR fields to expected fields
                    mapped_option = {
                        'contractSymbol': contract.localSymbol,
                        'strike': contract.strike,
                        'lastPrice': ticker.last if not np.isnan(ticker.last) else None,
                        'bid': ticker.bid if not np.isnan(ticker.bid) else None,
                        'ask': ticker.ask if not np.isnan(ticker.ask) else None,
                        'volume': ticker.volume if not np.isnan(ticker.volume) else None,
                        # 'openInterest': ??? # OI might require reqMktData snapshot or separate call? Check docs. Defaulting to 0.
                        'openInterest': 0,
                        'impliedVolatility': ticker.modelGreeks.impliedVol if ticker.modelGreeks.impliedVol and not np.isnan(ticker.modelGreeks.impliedVol) else None,
                        'delta': ticker.modelGreeks.delta if ticker.modelGreeks.delta and not np.isnan(ticker.modelGreeks.delta) else None,
                        'gamma': ticker.modelGreeks.gamma if ticker.modelGreeks.gamma and not np.isnan(ticker.modelGreeks.gamma) else None,
                        'theta': ticker.modelGreeks.theta if ticker.modelGreeks.theta and not np.isnan(ticker.modelGreeks.theta) else None,
                        'vega': ticker.modelGreeks.vega if ticker.modelGreeks.vega and not np.isnan(ticker.modelGreeks.vega) else None,
                    }
                    # Remove None values if calculations expect numbers
                    mapped_option = {k: v for k, v in mapped_option.items() if v is not None}

                    if contract.right == 'C':
                        calls.append(mapped_option)
                    elif contract.right == 'P':
                        puts.append(mapped_option)

                if not calls and not puts:
                     raise ValueError("Parsed IBKR data resulted in empty calls and puts lists.")

                logger.info(f"Successfully fetched options chain for {self.symbol} from IBKR (Expiration: {expiration}).")
                
                # Format expiration back to YYYY-MM-DD for consistency if needed
                formatted_expiration = f"{expiration[:4]}-{expiration[4:6]}-{expiration[6:]}"

                result = {
                    'symbol': self.symbol,
                    'expiration': formatted_expiration,
                    'current_price': current_price,
                    'timestamp': datetime.now().isoformat(),
                    'calls': calls,
                    'puts': puts,
                    'source': 'IBKR' # Add source indicator
                }
                self.cache.set_cache(cache_key, result)
                return result

            except ConnectionRefusedError:
                 logger.warning("IBKR connection refused. Ensure TWS/Gateway is running and API connections are enabled.")
            except ib.client.RequestError as ib_req_e:
                 logger.warning(f"IBKR request error for {self.symbol}: {ib_req_e}")
            except Exception as ib_e:
                logger.warning(f"IBKR options fetch failed for {self.symbol}: {ib_e}. Falling back to FMP.")
            finally:
                 if ib and ib.isConnected():
                      ib.disconnect() # Ensure disconnection

        # --- Try FMP Second ---
        if self.fmp_api_key:
            logger.debug(f"Attempting to fetch options chain for {self.symbol} from FMP.")
            try:
                # 1. Get available expiration dates from FMP
                exp_url = f"https://financialmodelingprep.com/api/v3/stock_option_chain/{self.symbol}?apikey={self.fmp_api_key}"
                exp_response = requests.get(exp_url, timeout=10)
                exp_response.raise_for_status()
                exp_data = exp_response.json()
                
                available_expirations = exp_data.get('options', []) # Assuming FMP returns expirations here
                if not available_expirations:
                     raise ValueError("No expiration dates found from FMP.")

                # Determine expiration date to use
                if expiration is None:
                    # Find nearest expiration (assuming sorted or find min date > today)
                    # This logic might need refinement based on FMP's actual response format
                    today = datetime.now().date()
                    future_expirations = [exp for exp in available_expirations if datetime.strptime(exp, '%Y-%m-%d').date() >= today]
                    if not future_expirations:
                         raise ValueError("No future expiration dates found from FMP.")
                    expiration = min(future_expirations) # Simplistic nearest, might need adjustment
                    logger.info(f"Using nearest FMP expiration date for {self.symbol}: {expiration}")
                elif expiration not in available_expirations:
                     raise ValueError(f"Specified expiration {expiration} not found in FMP available dates.")

                # 2. Get options chain for the specific expiration from FMP
                chain_url = f"https://financialmodelingprep.com/api/v3/options/chain/{self.symbol}?date={expiration}&apikey={self.fmp_api_key}"
                chain_response = requests.get(chain_url, timeout=15)
                chain_response.raise_for_status()
                chain_data = chain_response.json() # Assuming FMP returns a list of options dicts

                if not chain_data:
                    raise ValueError(f"No options chain data returned from FMP for {self.symbol} on {expiration}.")

                # 3. Process FMP data into the expected format (calls/puts lists)
                calls = []
                puts = []
                current_price = None # Try to get from FMP data if available, else fetch separately
                
                # FMP structure might differ - adjust parsing logic based on actual API response
                # Example assumes chain_data is a list of option contracts
                for option in chain_data:
                     # Attempt to get current price from one of the options (might not be reliable)
                     if current_price is None and 'lastTradePrice' in option: # Or underlyingPrice? Check FMP docs
                          # This assumes lastTradePrice is close enough to current underlying price
                          # A separate price fetch might be more robust
                          pass # current_price = option['lastTradePrice']

                     # Map FMP fields to expected fields (gamma, openInterest, volume, impliedVolatility, etc.)
                     # This requires knowing FMP's exact field names!
                     mapped_option = {
                         'contractSymbol': option.get('contractName'), # Adjust field names
                         'strike': option.get('strike'),
                         'lastPrice': option.get('lastTradePrice'),
                         'bid': option.get('bid'),
                         'ask': option.get('ask'),
                         'change': option.get('change'),
                         'percentChange': option.get('percentChange'),
                         'volume': option.get('volume'),
                         'openInterest': option.get('openInterest'),
                         'impliedVolatility': option.get('impliedVolatility'),
                         'delta': option.get('delta'),
                         'gamma': option.get('gamma'),
                         'theta': option.get('theta'),
                         'vega': option.get('vega'),
                         # Add other relevant fields if needed
                     }
                     # Remove None values if calculations expect numbers
                     mapped_option = {k: v for k, v in mapped_option.items() if v is not None}

                     if option.get('optionType') == 'call':
                         calls.append(mapped_option)
                     elif option.get('optionType') == 'put':
                         puts.append(mapped_option)

                if not calls and not puts:
                     raise ValueError("Parsed FMP data resulted in empty calls and puts lists.")

                # Fetch current price separately if not reliably available in options data
                if current_price is None:
                    current_price = self.get_current_price()
                    if current_price is None:
                         raise ValueError(f"Failed to get current price for {self.symbol} after FMP fetch.")

                logger.info(f"Successfully fetched options chain for {self.symbol} from FMP (Expiration: {expiration}).")
                
                result = {
                    'symbol': self.symbol,
                    'expiration': expiration,
                    'current_price': current_price,
                    'timestamp': datetime.now().isoformat(),
                    'calls': calls,
                    'puts': puts,
                    'source': 'FMP' # Add source indicator
                }
                self.cache.set_cache(cache_key, result)
                return result

            except Exception as fmp_e:
                logger.warning(f"FMP options fetch failed for {self.symbol}: {fmp_e}. Falling back to yfinance.")

        # --- Fallback to yfinance ---
        logger.debug(f"Attempting to fetch options chain for {self.symbol} from yfinance.")
        try:
            ticker = yf.Ticker(self.symbol)
            
            if expiration is None:
                expirations = ticker.options
                if not expirations:
                    logger.error(f"No options expiration dates found via yfinance for {self.symbol}")
                    return None
                expiration = expirations[0] # Use nearest
                logger.info(f"Using nearest yfinance expiration date for {self.symbol}: {expiration}")

            options = ticker.option_chain(expiration)
            if options.calls.empty and options.puts.empty:
                 logger.error(f"No options chain data found via yfinance for {self.symbol} on {expiration}")
                 return None

            calls = options.calls.to_dict('records')
            puts = options.puts.to_dict('records')
            current_price = self.get_current_price()
            if current_price is None:
                 raise ValueError(f"Failed to get current price for {self.symbol} via yfinance.")

            logger.info(f"Successfully fetched options chain for {self.symbol} from yfinance (Expiration: {expiration}).")

            result = {
                'symbol': self.symbol,
                'expiration': expiration,
                'current_price': current_price,
                'timestamp': datetime.now().isoformat(),
                'calls': calls,
                'puts': puts,
                'source': 'yfinance' # Add source indicator
            }
            self.cache.set_cache(cache_key, result)
            return result
            
        except Exception as yf_e:
            logger.error(f"yfinance options fetch failed for {self.symbol}: {yf_e}")
            return None
    
    def calculate_metrics(self, expiration=None):
        """
        Calculate all advanced options metrics
        
        Args:
            expiration (str, optional): Expiration date in YYYY-MM-DD format
            
        Returns:
            dict: Calculated metrics
        """
        # Get options chain
        options_chain = self.get_options_chain(expiration)
        if not options_chain:
            logger.error(f"Could not get options chain for {self.symbol}")
            return None
            
        # Calculate metrics
        metrics = {
            'symbol': self.symbol,
            'current_price': options_chain['current_price'],
            'expiration': options_chain['expiration'],
            'timestamp': datetime.now().isoformat()
        }
        
        # Calculate gamma profile
        gamma_profile = self.calculate_gamma_profile(options_chain)
        metrics['gamma_profile'] = gamma_profile
        
        # Calculate high gamma strikes
        high_gamma_strikes = self.calculate_high_gamma_strikes(gamma_profile)
        metrics['high_gamma_strikes'] = high_gamma_strikes
        
        # Calculate GEX
        gex = self.calculate_gex(options_chain)
        metrics['gex'] = gex
        
        # Calculate VWIV
        vwiv = self.calculate_vwiv(options_chain)
        metrics['vwiv'] = vwiv
        
        # Calculate second-order Greeks
        charm = self.calculate_charm(options_chain)
        metrics['charm'] = charm
        
        vanna = self.calculate_vanna(options_chain)
        metrics['vanna'] = vanna
        
        vomma = self.calculate_vomma(options_chain)
        metrics['vomma'] = vomma

        # Calculate total open interest
        total_open_interest = 0
        for option_type in ['calls', 'puts']:
            for option in options_chain.get(option_type, []):
                total_open_interest += option.get('openInterest', 0) or 0 # Handle None or missing key
        metrics['total_open_interest'] = total_open_interest
        
        return metrics
        
    def calculate_gamma_profile(self, options_chain):
        """
        Calculate gamma profile across all strikes
        
        Args:
            options_chain (dict): Options chain data
            
        Returns:
            dict: Gamma profile by strike
        """
        gamma_profile = {}
        current_price = options_chain['current_price']
        
        # Process calls and puts
        for option_type, options in [('calls', options_chain['calls']), ('puts', options_chain['puts'])]:
            for option in options:
                strike = option['strike']
                gamma = option.get('gamma', 0)
                volume = option.get('volume', 0) or 0
                open_interest = option.get('openInterest', 0) or 0
                
                if strike not in gamma_profile:
                    gamma_profile[strike] = {
                        'total_gamma': 0,
                        'call_gamma': 0,
                        'put_gamma': 0,
                        'distance_from_price': abs(strike - current_price) / current_price
                    }
                
                gamma_profile[strike]['total_gamma'] += gamma * open_interest
                if option_type == 'calls':
                    gamma_profile[strike]['call_gamma'] += gamma * open_interest
                else:
                    gamma_profile[strike]['put_gamma'] += gamma * open_interest
        
        # Convert to list for easier sorting
        gamma_list = [{'strike': k, **v} for k, v in gamma_profile.items()]
        gamma_list.sort(key=lambda x: x['strike'])
        
        return gamma_list
        
    def calculate_high_gamma_strikes(self, gamma_profile, threshold_percentile=90):
        """
        Calculate high gamma strikes
        
        Args:
            gamma_profile (list): Gamma profile data
            threshold_percentile (int): Percentile threshold for high gamma
            
        Returns:
            list: High gamma strikes
        """
        if not gamma_profile:
            return []
            
        # Extract total gamma values
        gamma_values = [item['total_gamma'] for item in gamma_profile]
        
        # Calculate threshold
        threshold = np.percentile(gamma_values, threshold_percentile)
        
        # Filter strikes with gamma above threshold
        high_gamma_strikes = [
            item['strike'] for item in gamma_profile 
            if item['total_gamma'] >= threshold
        ]
        
        return high_gamma_strikes
        
    def calculate_gex(self, options_chain):
        """
        Calculate Gamma Exposure (GEX) profile
        
        Args:
            options_chain (dict): Options chain data
            
        Returns:
            dict: GEX profile
        """
        gex_profile = {}
        current_price = options_chain['current_price']
        found_valid_gamma_oi = False # Flag for logging
        
        # Process calls (positive GEX)
        for call in options_chain.get('calls', []): # Use .get for safety
            strike = call['strike']
            gamma = call.get('gamma', 0)
            open_interest = call.get('openInterest', 0) or 0
            
            # Check if we found valid data for logging
            if gamma != 0 and open_interest != 0:
                found_valid_gamma_oi = True
                
            call_gex = gamma * open_interest * 100 * current_price / 10000
            
            if strike not in gex_profile:
                gex_profile[strike] = {'total_gex': 0, 'call_gex': 0, 'put_gex': 0}
                
            gex_profile[strike]['total_gex'] += call_gex
            gex_profile[strike]['call_gex'] += call_gex
            
        # Process puts (negative GEX)
        for put in options_chain.get('puts', []): # Use .get for safety
            strike = put['strike']
            gamma = put.get('gamma', 0)
            open_interest = put.get('openInterest', 0) or 0

            # Check if we found valid data for logging
            if gamma != 0 and open_interest != 0:
                found_valid_gamma_oi = True
            
            put_gex = -gamma * open_interest * 100 * current_price / 10000
            
            if strike not in gex_profile:
                gex_profile[strike] = {'total_gex': 0, 'call_gex': 0, 'put_gex': 0}
                
            gex_profile[strike]['total_gex'] += put_gex
            gex_profile[strike]['put_gex'] += put_gex
            
        # Calculate total GEX
        total_gex = sum(item['total_gex'] for item in gex_profile.values())
        
        # Convert to list for easier sorting
        gex_list = [{'strike': k, **v} for k, v in gex_profile.items()]
        gex_list.sort(key=lambda x: x['strike'])

        # Log warning if GEX is zero due to missing/zero input data
        if total_gex == 0 and not found_valid_gamma_oi:
            logger.warning(f"GEX calculation for {self.symbol} resulted in 0. "
                           "This might be due to missing or zero gamma/openInterest data in the options chain.")
        
        return {
            'total_gex': total_gex,
            'gex_by_strike': gex_list,
            'gex_direction': 'positive' if total_gex > 0 else ('negative' if total_gex < 0 else 'neutral') # Handle zero case
        }
        
    def calculate_charm(self, options_chain):
        """
        Calculate Charm (delta decay) for all options
        
        Args:
            options_chain (dict): Options chain data
            
        Returns:
            dict: Charm data by strike
        """
        charm_profile = {}
        current_price = options_chain['current_price']
        
        # Process calls and puts
        for option_type, options in [('calls', options_chain['calls']), ('puts', options_chain['puts'])]:
            for option in options:
                strike = option['strike']
                delta = option.get('delta', 0)
                theta = option.get('theta', 0)
                open_interest = option.get('openInterest', 0) or 0
                
                if strike not in charm_profile:
                    charm_profile[strike] = {
                        'total_charm': 0,
                        'call_charm': 0,
                        'put_charm': 0
                    }
                
                # Charm is the rate of change of delta with respect to time
                # For simplicity, we'll use theta as a proxy for time decay
                charm = -theta * (delta / (current_price * 0.01)) if current_price > 0 else 0
                
                charm_profile[strike]['total_charm'] += charm * open_interest
                if option_type == 'calls':
                    charm_profile[strike]['call_charm'] += charm * open_interest
                else:
                    charm_profile[strike]['put_charm'] += charm * open_interest
        
        # Convert to list for easier sorting
        charm_list = [{'strike': k, **v} for k, v in charm_profile.items()]
        charm_list.sort(key=lambda x: x['strike'])
        
        return charm_list
        
    def calculate_vanna(self, options_chain):
        """
        Calculate Vanna (delta sensitivity to volatility) for all options
        
        Args:
            options_chain (dict): Options chain data
            
        Returns:
            dict: Vanna data by strike
        """
        vanna_profile = {}
        current_price = options_chain['current_price']
        
        # Process calls and puts
        for option_type, options in [('calls', options_chain['calls']), ('puts', options_chain['puts'])]:
            for option in options:
                strike = option['strike']
                delta = option.get('delta', 0)
                vega = option.get('vega', 0)
                open_interest = option.get('openInterest', 0) or 0
                
                if strike not in vanna_profile:
                    vanna_profile[strike] = {
                        'total_vanna': 0,
                        'call_vanna': 0,
                        'put_vanna': 0
                    }
                
                # Vanna is the rate of change of delta with respect to volatility
                vanna = vega * (delta / (current_price * 0.01)) if current_price > 0 else 0
                
                vanna_profile[strike]['total_vanna'] += vanna * open_interest
                if option_type == 'calls':
                    vanna_profile[strike]['call_vanna'] += vanna * open_interest
                else:
                    vanna_profile[strike]['put_vanna'] += vanna * open_interest
        
        # Convert to list for easier sorting
        vanna_list = [{'strike': k, **v} for k, v in vanna_profile.items()]
        vanna_list.sort(key=lambda x: x['strike'])
        
        return vanna_list
        
    def calculate_vomma(self, options_chain):
        """
        Calculate Vomma (vega sensitivity to volatility) for all options
        
        Args:
            options_chain (dict): Options chain data
            
        Returns:
            dict: Vomma data by strike
        """
        vomma_profile = {}
        current_price = options_chain['current_price']
        
        # Process calls and puts
        for option_type, options in [('calls', options_chain['calls']), ('puts', options_chain['puts'])]:
            for option in options:
                strike = option['strike']
                vega = option.get('vega', 0)
                iv = option.get('impliedVolatility', 0)
                open_interest = option.get('openInterest', 0) or 0
                
                if strike not in vomma_profile:
                    vomma_profile[strike] = {
                        'total_vomma': 0,
                        'call_vomma': 0,
                        'put_vomma': 0
                    }
                
                # Vomma is the rate of change of vega with respect to volatility
                vomma = vega * (iv / 100) if iv > 0 else 0
                
                vomma_profile[strike]['total_vomma'] += vomma * open_interest
                if option_type == 'calls':
                    vomma_profile[strike]['call_vomma'] += vomma * open_interest
                else:
                    vomma_profile[strike]['put_vomma'] += vomma * open_interest
        
        # Convert to list for easier sorting
        vomma_list = [{'strike': k, **v} for k, v in vomma_profile.items()]
        vomma_list.sort(key=lambda x: x['strike'])
        
        return vomma_list
        
    def calculate_vwiv(self, options_chain):
        """
        Calculate Volume-Weighted Implied Volatility (VWIV)
        
        Args:
            options_chain (dict): Options chain data
            
        Returns:
            dict: VWIV data
        """
        total_weighted_iv = 0
        total_volume = 0
        found_valid_iv_volume = False # Flag for logging
        
        # Process all options
        for option_type in ['calls', 'puts']:
            for option in options_chain.get(option_type, []): # Use .get for safety
                iv = option.get('impliedVolatility', 0)
                volume = option.get('volume', 0) or 0
                
                if iv > 0 and volume > 0:
                    found_valid_iv_volume = True # Mark that we found usable data
                    total_weighted_iv += iv * volume
                    total_volume += volume
                    
        # Calculate VWIV
        vwiv = total_weighted_iv / total_volume if total_volume > 0 else 0

        # Log warning if VWIV is zero due to missing/zero input data
        if vwiv == 0 and not found_valid_iv_volume:
             logger.warning(f"VWIV calculation for {self.symbol} resulted in 0. "
                            "This might be due to missing or zero impliedVolatility/volume data in the options chain.")
        
        return {
            'vwiv': vwiv,
            'total_volume': total_volume
        }
