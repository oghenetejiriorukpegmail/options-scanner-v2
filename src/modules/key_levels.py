"""
Key Levels Mapping Module

This module uses options chain data to pinpoint critical support and resistance levels.
"""

import logging
import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

class KeyLevelsMapper:
    """
    Maps key price levels using options chain data
    
    Features:
    - Options Chain Analysis (OI, volume, Greeks)
    - Max Pain Calculation
    """
    
    def __init__(self, symbol):
        """
        Initialize the Key Levels Mapper
        
        Args:
            symbol (str): Stock symbol to analyze
        """
        self.symbol = symbol
        self.ticker = yf.Ticker(symbol)
        self.price_data = None
        self.options_data = {}
        self.support_levels = []
        self.resistance_levels = []
        self.max_pain = None
        
    def _fetch_data(self):
        """Fetch price data and options chain data"""
        logger.info(f"Fetching options data for {self.symbol}")
        
        # Fetch current price data
        self.price_data = self.ticker.history(period="5d")
        if self.price_data.empty:
            logger.error(f"Failed to fetch price data for {self.symbol}")
            return False
            
        # Get current price
        self.current_price = self.price_data['Close'].iloc[-1]
        
        # Fetch options expiration dates
        try:
            expiration_dates = self.ticker.options
            
            if not expiration_dates:
                logger.error(f"No options data available for {self.symbol}")
                return False
                
            # Get data for the nearest 3 expiration dates
            for date in expiration_dates[:3]:
                option_chain = self.ticker.option_chain(date)
                self.options_data[date] = {
                    'calls': option_chain.calls,
                    'puts': option_chain.puts
                }
                
            return True
        except Exception as e:
            logger.error(f"Error fetching options data: {e}")
            return False
    
    def _calculate_max_pain(self):
        """
        Calculate the max pain point
        
        Max Pain is the strike price where option writers (sellers) would
        lose the least amount of money if all options expired at that price.
        """
        # Use the nearest expiration date
        nearest_date = list(self.options_data.keys())[0]
        calls = self.options_data[nearest_date]['calls']
        puts = self.options_data[nearest_date]['puts']
        
        # Get unique strike prices
        strikes = sorted(set(calls['strike'].tolist() + puts['strike'].tolist()))
        
        # Calculate pain for each strike price
        pain = []
        for strike in strikes:
            # Calculate call pain (loss to call writers if price ends at this strike)
            call_pain = sum(calls['openInterest'] * np.maximum(0, strike - calls['strike']))
            
            # Calculate put pain (loss to put writers if price ends at this strike)
            put_pain = sum(puts['openInterest'] * np.maximum(0, puts['strike'] - strike))
            
            # Total pain
            total_pain = call_pain + put_pain
            pain.append((strike, total_pain))
        
        # Find the strike with minimum pain
        if pain:
            self.max_pain = min(pain, key=lambda x: x[1])[0]
        else:
            self.max_pain = self.current_price
    
    def _identify_support_resistance(self):
        """Identify support and resistance levels based on options data"""
        # Use the nearest expiration date
        nearest_date = list(self.options_data.keys())[0]
        calls = self.options_data[nearest_date]['calls']
        puts = self.options_data[nearest_date]['puts']
        
        # Sort by open interest
        high_oi_calls = calls.sort_values('openInterest', ascending=False).head(5)
        high_oi_puts = puts.sort_values('openInterest', ascending=False).head(5)
        
        # Identify potential resistance levels (call strikes above current price)
        resistance_candidates = high_oi_calls[high_oi_calls['strike'] > self.current_price]['strike'].tolist()
        
        # Identify potential support levels (put strikes below current price)
        support_candidates = high_oi_puts[high_oi_puts['strike'] < self.current_price]['strike'].tolist()
        
        # Add levels with high gamma as they act as magnets
        if 'gamma' in calls.columns and 'gamma' in puts.columns:
            high_gamma_calls = calls[calls['gamma'] > 0.05]['strike'].tolist()
            high_gamma_puts = puts[puts['gamma'] > 0.05]['strike'].tolist()
            
            resistance_candidates.extend([s for s in high_gamma_calls if s > self.current_price])
            support_candidates.extend([s for s in high_gamma_puts if s < self.current_price])
        
        # Remove duplicates and sort
        self.resistance_levels = sorted(set(resistance_candidates))
        self.support_levels = sorted(set(support_candidates), reverse=True)
    
    def _calculate_greeks(self):
        """
        Calculate and analyze key Greeks
        
        This is a simplified implementation. In a real-world scenario,
        you would use more sophisticated models or data sources.
        """
        # For demonstration purposes, we'll just identify strikes with high gamma
        # In a real implementation, you would calculate charm, vanna, vomma, etc.
        
        high_gamma_strikes = []
        
        for date, data in self.options_data.items():
            calls = data['calls']
            puts = data['puts']
            
            if 'gamma' in calls.columns and 'gamma' in puts.columns:
                # Find strikes with high gamma (> 0.05)
                high_gamma_calls = calls[calls['gamma'] > 0.05]['strike'].tolist()
                high_gamma_puts = puts[puts['gamma'] > 0.05]['strike'].tolist()
                
                high_gamma_strikes.extend(high_gamma_calls)
                high_gamma_strikes.extend(high_gamma_puts)
        
        return sorted(set(high_gamma_strikes))
    
    def map_levels(self):
        """
        Map key price levels
        
        Returns:
            dict: Mapping results
        """
        if not self._fetch_data():
            return {
                'support': [],
                'resistance': [],
                'max_pain': None,
                'high_gamma': [],
                'success': False
            }
            
        self._calculate_max_pain()
        self._identify_support_resistance()
        high_gamma_strikes = self._calculate_greeks()
        
        return {
            'support': self.support_levels,
            'resistance': self.resistance_levels,
            'max_pain': self.max_pain,
            'high_gamma': high_gamma_strikes,
            'current_price': self.current_price,
            'success': True
        }