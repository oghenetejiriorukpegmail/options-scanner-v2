"""
Confirmation and Timing Module

This module provides entry and exit signals for trade setups.
"""

import logging
import numpy as np
import pandas as pd
import yfinance as yf
from ta.momentum import StochasticOscillator

logger = logging.getLogger(__name__)

class ConfirmationModule:
    """
    Provides entry and exit signals for trade setups
    
    Features:
    - Entry Triggers
    - Exit Triggers
    """
    
    def __init__(self, symbol, lookback_period=30):
        """
        Initialize the Confirmation Module
        
        Args:
            symbol (str): Stock symbol to analyze
            lookback_period (int): Number of days to look back
        """
        self.symbol = symbol
        self.lookback_period = lookback_period
        self.data = None
        self.ticker = yf.Ticker(symbol)
    
    def _fetch_data(self):
        """Fetch historical price data and calculate indicators"""
        logger.info(f"Fetching confirmation data for {self.symbol}")
        
        # Fetch historical price data
        self.data = self.ticker.history(period=f"{self.lookback_period}d")
        
        if self.data.empty:
            logger.error(f"Failed to fetch data for {self.symbol}")
            return False
        
        # Calculate Stochastic RSI
        # First calculate RSI
        delta = self.data['Close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        
        rs = avg_gain / avg_loss
        self.data['RSI'] = 100 - (100 / (1 + rs))
        
        # Then calculate Stochastic RSI
        stoch = StochasticOscillator(
            high=self.data['RSI'],
            low=self.data['RSI'],
            close=self.data['RSI'],
            window=14,
            smooth_window=3
        )
        self.data['Stoch_RSI'] = stoch.stoch()
        self.data['Stoch_RSI_D'] = stoch.stoch_signal()
        
        # Calculate volume metrics
        self.data['Volume_SMA'] = self.data['Volume'].rolling(window=20).mean()
        self.data['Volume_Ratio'] = self.data['Volume'] / self.data['Volume_SMA']
        
        return True
    
    def _check_bullish_entry(self, setup_results):
        """
        Check for bullish entry signals
        
        Args:
            setup_results (dict): Trade setup results
            
        Returns:
            tuple: (has_signal, signal_strength, reasons)
        """
        if not self.data is not None or len(self.data) < 5:
            return False, 0, ["Insufficient data"]
        
        reasons = []
        signal_strength = 0
        
        # Get the latest data points
        latest = self.data.iloc[-1]
        prev = self.data.iloc[-2]
        
        # Check for Stochastic RSI hook up from below 60
        if prev['Stoch_RSI'] < 60 and latest['Stoch_RSI'] > prev['Stoch_RSI'] and latest['Stoch_RSI_D'] > prev['Stoch_RSI_D']:
            reasons.append("Stochastic RSI hooking up from below 60")
            signal_strength += 30
        
        # Check for volume spike
        if latest['Volume_Ratio'] > 1.5:
            reasons.append(f"Volume spike ({latest['Volume_Ratio']:.2f}x average)")
            signal_strength += 20
        
        # Check for price near support
        if 'support' in setup_results and setup_results['support'] and abs(latest['Close'] - setup_results['support'][0]) / setup_results['support'][0] < 0.02:
            reasons.append(f"Price near support level ({setup_results['support'][0]:.2f})")
            signal_strength += 25
        
        # Check for price above key EMAs
        if 'ema10' in setup_results and 'ema20' in setup_results:
            if latest['Close'] > setup_results['ema10'] and latest['Close'] > setup_results['ema20']:
                reasons.append("Price above key EMAs")
                signal_strength += 15
        
        # Check for RSI momentum
        if 'rsi' in setup_results and setup_results['rsi'] > prev['RSI'] and setup_results['rsi'] > 50:
            reasons.append(f"RSI showing upward momentum ({setup_results['rsi']:.2f})")
            signal_strength += 10
        
        # Determine if we have a signal (strength > 50)
        has_signal = signal_strength > 50
        
        return has_signal, signal_strength, reasons
    
    def _check_bearish_entry(self, setup_results):
        """
        Check for bearish entry signals
        
        Args:
            setup_results (dict): Trade setup results
            
        Returns:
            tuple: (has_signal, signal_strength, reasons)
        """
        if not self.data is not None or len(self.data) < 5:
            return False, 0, ["Insufficient data"]
        
        reasons = []
        signal_strength = 0
        
        # Get the latest data points
        latest = self.data.iloc[-1]
        prev = self.data.iloc[-2]
        
        # Check for Stochastic RSI hook down from above 40
        if prev['Stoch_RSI'] > 40 and latest['Stoch_RSI'] < prev['Stoch_RSI'] and latest['Stoch_RSI_D'] < prev['Stoch_RSI_D']:
            reasons.append("Stochastic RSI hooking down from above 40")
            signal_strength += 30
        
        # Check for volume spike
        if latest['Volume_Ratio'] > 1.5:
            reasons.append(f"Volume spike ({latest['Volume_Ratio']:.2f}x average)")
            signal_strength += 20
        
        # Check for price near resistance
        if 'resistance' in setup_results and setup_results['resistance'] and abs(latest['Close'] - setup_results['resistance'][0]) / setup_results['resistance'][0] < 0.02:
            reasons.append(f"Price near resistance level ({setup_results['resistance'][0]:.2f})")
            signal_strength += 25
        
        # Check for price below key EMAs
        if 'ema10' in setup_results and 'ema20' in setup_results:
            if latest['Close'] < setup_results['ema10'] and latest['Close'] < setup_results['ema20']:
                reasons.append("Price below key EMAs")
                signal_strength += 15
        
        # Check for RSI momentum
        if 'rsi' in setup_results and setup_results['rsi'] < prev['RSI'] and setup_results['rsi'] < 50:
            reasons.append(f"RSI showing downward momentum ({setup_results['rsi']:.2f})")
            signal_strength += 10
        
        # Determine if we have a signal (strength > 50)
        has_signal = signal_strength > 50
        
        return has_signal, signal_strength, reasons
    
    def _check_neutral_entry(self, setup_results):
        """
        Check for neutral entry signals
        
        Args:
            setup_results (dict): Trade setup results
            
        Returns:
            tuple: (has_signal, signal_strength, reasons)
        """
        if not self.data is not None or len(self.data) < 5:
            return False, 0, ["Insufficient data"]
        
        reasons = []
        signal_strength = 0
        
        # Get the latest data points
        latest = self.data.iloc[-1]
        
        # Check for price near Max Pain
        if 'max_pain' in setup_results and setup_results['max_pain'] and abs(latest['Close'] - setup_results['max_pain']) / setup_results['max_pain'] < 0.01:
            reasons.append(f"Price stalling at Max Pain ({setup_results['max_pain']:.2f})")
            signal_strength += 40
        
        # Check for low volatility
        if 'vwiv' in setup_results and setup_results['vwiv'] < 0.3:
            reasons.append(f"Low implied volatility ({setup_results['vwiv']:.2f})")
            signal_strength += 20
        
        # Check for RSI in neutral zone
        if 'rsi' in setup_results and 45 <= setup_results['rsi'] <= 55:
            reasons.append(f"RSI in neutral zone ({setup_results['rsi']:.2f})")
            signal_strength += 20
        
        # Check for Stochastic RSI in neutral zone
        if 'stoch_rsi' in setup_results and 40 <= setup_results['stoch_rsi'] <= 60:
            reasons.append(f"Stochastic RSI in neutral zone ({setup_results['stoch_rsi']:.2f})")
            signal_strength += 20
        
        # Determine if we have a signal (strength > 50)
        has_signal = signal_strength > 50
        
        return has_signal, signal_strength, reasons
    
    def _check_exit_signals(self, setup_type, setup_results):
        """
        Check for exit signals
        
        Args:
            setup_type (str): Type of setup (bullish, bearish, neutral)
            setup_results (dict): Trade setup results
            
        Returns:
            tuple: (has_signal, signal_strength, reasons)
        """
        if not self.data is not None or len(self.data) < 5:
            return False, 0, ["Insufficient data"]
        
        reasons = []
        signal_strength = 0
        
        # Get the latest data points
        latest = self.data.iloc[-1]
        prev = self.data.iloc[-2]
        
        # Check for RSI extremes
        if 'rsi' in setup_results:
            if setup_type.startswith('bullish') and setup_results['rsi'] > 80:
                reasons.append(f"RSI overbought ({setup_results['rsi']:.2f})")
                signal_strength += 30
            elif setup_type.startswith('bearish') and setup_results['rsi'] < 20:
                reasons.append(f"RSI oversold ({setup_results['rsi']:.2f})")
                signal_strength += 30
        
        # Check for Stochastic RSI reversals
        if setup_type.startswith('bullish') and prev['Stoch_RSI'] > latest['Stoch_RSI'] and prev['Stoch_RSI'] > 80:
            reasons.append("Stochastic RSI reversing from overbought")
            signal_strength += 25
        elif setup_type.startswith('bearish') and prev['Stoch_RSI'] < latest['Stoch_RSI'] and prev['Stoch_RSI'] < 20:
            reasons.append("Stochastic RSI reversing from oversold")
            signal_strength += 25
        
        # Check for price reaching key levels
        if setup_type.startswith('bullish') and 'resistance' in setup_results and setup_results['resistance']:
            if abs(latest['Close'] - setup_results['resistance'][0]) / setup_results['resistance'][0] < 0.01:
                reasons.append(f"Price reaching resistance ({setup_results['resistance'][0]:.2f})")
                signal_strength += 25
        elif setup_type.startswith('bearish') and 'support' in setup_results and setup_results['support']:
            if abs(latest['Close'] - setup_results['support'][0]) / setup_results['support'][0] < 0.01:
                reasons.append(f"Price reaching support ({setup_results['support'][0]:.2f})")
                signal_strength += 25
        
        # Check for trend reversal
        if setup_type.startswith('bullish') and 'ema10' in setup_results and 'ema20' in setup_results:
            if latest['Close'] < setup_results['ema10'] and prev['Close'] > prev['ema10']:
                reasons.append("Price breaking below 10 EMA")
                signal_strength += 20
        elif setup_type.startswith('bearish') and 'ema10' in setup_results and 'ema20' in setup_results:
            if latest['Close'] > setup_results['ema10'] and prev['Close'] < prev['ema10']:
                reasons.append("Price breaking above 10 EMA")
                signal_strength += 20
        
        # Determine if we have a signal (strength > 50)
        has_signal = signal_strength > 50
        
        return has_signal, signal_strength, reasons
    
    def get_signals(self, setup_results):
        """
        Get entry and exit signals
        
        Args:
            setup_results (dict): Trade setup results
            
        Returns:
            dict: Signal results
        """
        if not self._fetch_data():
            return {
                'entry': {
                    'signal': False,
                    'strength': 0,
                    'reasons': ["Failed to fetch data"]
                },
                'exit': {
                    'signal': False,
                    'strength': 0,
                    'reasons': ["Failed to fetch data"]
                },
                'success': False
            }
        
        setup_type = setup_results.get('setup', 'unknown')
        
        # Check for entry signals based on setup type
        if setup_type.startswith('bullish'):
            entry_signal, entry_strength, entry_reasons = self._check_bullish_entry(setup_results)
        elif setup_type.startswith('bearish'):
            entry_signal, entry_strength, entry_reasons = self._check_bearish_entry(setup_results)
        elif setup_type.startswith('neutral'):
            entry_signal, entry_strength, entry_reasons = self._check_neutral_entry(setup_results)
        else:
            entry_signal, entry_strength, entry_reasons = False, 0, ["Unknown setup type"]
        
        # Check for exit signals
        exit_signal, exit_strength, exit_reasons = self._check_exit_signals(setup_type, setup_results)
        
        return {
            'entry': {
                'signal': entry_signal,
                'strength': entry_strength,
                'reasons': entry_reasons
            },
            'exit': {
                'signal': exit_signal,
                'strength': exit_strength,
                'reasons': exit_reasons
            },
            'success': True
        }