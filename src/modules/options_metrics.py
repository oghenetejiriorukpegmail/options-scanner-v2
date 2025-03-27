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
                logger.info(f"Using cached options chain for {self.symbol}")
                return cached_data
                
        try:
            ticker = yf.Ticker(self.symbol)
            
            # Get all expiration dates if none specified
            if expiration is None:
                expirations = ticker.options
                if not expirations:
                    logger.error(f"No options data available for {self.symbol}")
                    return None
                    
                # Use nearest expiration
                expiration = expirations[0]
                
            # Get options chain
            options = ticker.option_chain(expiration)
            
            # Convert to dict for easier handling
            calls = options.calls.to_dict('records')
            puts = options.puts.to_dict('records')
            
            # Calculate Greeks if needed
            current_price = self.get_current_price()
            
            result = {
                'symbol': self.symbol,
                'expiration': expiration,
                'current_price': current_price,
                'timestamp': datetime.now().isoformat(),
                'calls': calls,
                'puts': puts
            }
            
            # Cache the result
            # Just use the set_cache method which now handles JSON serialization internally
            self.cache.set_cache(cache_key, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting options chain for {self.symbol}: {e}")
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
        
        # Process calls (positive GEX)
        for call in options_chain['calls']:
            strike = call['strike']
            gamma = call.get('gamma', 0)
            open_interest = call.get('openInterest', 0) or 0
            
            call_gex = gamma * open_interest * 100 * current_price / 10000
            
            if strike not in gex_profile:
                gex_profile[strike] = {'total_gex': 0, 'call_gex': 0, 'put_gex': 0}
                
            gex_profile[strike]['total_gex'] += call_gex
            gex_profile[strike]['call_gex'] += call_gex
            
        # Process puts (negative GEX)
        for put in options_chain['puts']:
            strike = put['strike']
            gamma = put.get('gamma', 0)
            open_interest = put.get('openInterest', 0) or 0
            
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
        
        return {
            'total_gex': total_gex,
            'gex_by_strike': gex_list,
            'gex_direction': 'positive' if total_gex > 0 else 'negative'
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
        
        # Process all options
        for option_type in ['calls', 'puts']:
            for option in options_chain[option_type]:
                iv = option.get('impliedVolatility', 0)
                volume = option.get('volume', 0) or 0
                
                if iv > 0 and volume > 0:
                    total_weighted_iv += iv * volume
                    total_volume += volume
                    
        # Calculate VWIV
        vwiv = total_weighted_iv / total_volume if total_volume > 0 else 0
        
        return {
            'vwiv': vwiv,
            'total_volume': total_volume
        }
