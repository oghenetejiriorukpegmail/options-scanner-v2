"""
Market Context Analysis Module

This module evaluates the market environment using technical indicators and options data.
"""

import logging
import numpy as np
import pandas as pd
import yfinance as yf
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator, StochasticOscillator

logger = logging.getLogger(__name__)

class MarketContextAnalyzer:
    """
    Analyzes market context using technical indicators and options data
    
    Features:
    - Trend Identification (EMAs)
    - Sentiment and Volatility (PCR, VWIV, GEX)
    - Momentum Assessment (RSI, Stochastic RSI)
    """
    
    def __init__(self, symbol, lookback_period=100):
        """
        Initialize the Market Context Analyzer
        
        Args:
            symbol (str): Stock symbol to analyze
            lookback_period (int): Number of days to look back
        """
        self.symbol = symbol
        self.lookback_period = lookback_period
        self.data = None
        self.options_data = None
        
    def _fetch_data(self):
        """Fetch historical price data and options data"""
        logger.info(f"Fetching data for {self.symbol}")
        
        # Fetch historical price data
        ticker = yf.Ticker(self.symbol)
        self.data = ticker.history(period=f"{self.lookback_period}d")
        
        if self.data.empty:
            logger.error(f"Failed to fetch data for {self.symbol}")
            return False
            
        # Fetch options data
        try:
            self.options_data = ticker.options
            if self.options_data:
                # Get the nearest expiration date
                expiration = self.options_data[0]
                
                # Fetch call and put options for the nearest expiration
                calls = ticker.option_chain(expiration).calls
                puts = ticker.option_chain(expiration).puts
                
                # Calculate Put-Call Ratio (PCR)
                self.pcr = puts['volume'].sum() / calls['volume'].sum() if calls['volume'].sum() > 0 else 0
                
                # Calculate Volume-Weighted Implied Volatility (VWIV)
                self.vwiv = (calls['impliedVolatility'] * calls['volume']).sum() / calls['volume'].sum() if calls['volume'].sum() > 0 else 0
                
                # For GEX, we would need more advanced data sources
                # This is a simplified placeholder
                self.gex = 0
            else:
                logger.warning(f"No options data available for {self.symbol}")
                self.pcr = 0
                self.vwiv = 0
                self.gex = 0
        except Exception as e:
            logger.error(f"Error fetching options data: {e}")
            self.pcr = 0
            self.vwiv = 0
            self.gex = 0
            
        return True
        
    def _calculate_indicators(self):
        """Calculate technical indicators"""
        # Calculate EMAs
        self.data['ema10'] = EMAIndicator(close=self.data['Close'], window=10).ema_indicator()
        self.data['ema20'] = EMAIndicator(close=self.data['Close'], window=20).ema_indicator()
        self.data['ema50'] = EMAIndicator(close=self.data['Close'], window=50).ema_indicator()
        
        # Calculate RSI
        self.data['rsi'] = RSIIndicator(close=self.data['Close'], window=14).rsi()
        
        # Calculate Stochastic RSI (simplified version)
        stoch = StochasticOscillator(
            high=self.data['rsi'],
            low=self.data['rsi'],
            close=self.data['rsi'],
            window=14,
            smooth_window=3
        )
        self.data['stoch_rsi'] = stoch.stoch()
        
    def _determine_trend(self):
        """
        Determine the trend based on EMA alignment
        
        Returns:
            str: 'bullish', 'bearish', or 'neutral'
        """
        latest = self.data.iloc[-1]
        
        # Check EMA alignment
        if latest['ema10'] > latest['ema20'] > latest['ema50']:
            return 'bullish'
        elif latest['ema10'] < latest['ema20'] < latest['ema50']:
            return 'bearish'
        else:
            # Check if EMAs are converging (within 1% of each other)
            ema_range = (max(latest['ema10'], latest['ema20'], latest['ema50']) - 
                         min(latest['ema10'], latest['ema20'], latest['ema50'])) / latest['ema20']
            if ema_range < 0.01:
                return 'neutral'
            
            # If not clearly aligned, use recent price action
            recent_change = (latest['Close'] - self.data.iloc[-5]['Close']) / self.data.iloc[-5]['Close']
            if recent_change > 0.02:  # 2% increase
                return 'bullish'
            elif recent_change < -0.02:  # 2% decrease
                return 'bearish'
            else:
                return 'neutral'
    
    def _determine_sentiment(self):
        """
        Determine market sentiment based on PCR and IV
        
        Returns:
            str: 'bullish', 'bearish', or 'neutral'
        """
        # Get current IV
        iv = self.vwiv
        
        # Adjust PCR thresholds based on IV
        if iv < 0.3:  # Low IV
            if self.pcr < 0.7:
                return 'bullish'
            elif self.pcr > 1.3:
                return 'bearish'
            else:
                return 'neutral'
        elif iv < 0.5:  # Moderate IV
            if self.pcr < 0.8:
                return 'bullish'
            elif self.pcr > 1.2:
                return 'bearish'
            else:
                return 'neutral'
        else:  # High IV
            if self.pcr < 0.5:
                return 'bullish'
            elif self.pcr > 1.5:
                return 'bearish'
            else:
                return 'neutral'
    
    def _determine_momentum(self):
        """
        Determine momentum based on RSI and Stochastic RSI
        
        Returns:
            str: 'bullish', 'bearish', or 'neutral'
        """
        latest = self.data.iloc[-1]
        rsi = latest['rsi']
        stoch_rsi = latest['stoch_rsi']
        
        # Check RSI
        if rsi > 70:
            rsi_signal = 'overbought'
        elif rsi < 30:
            rsi_signal = 'oversold'
        elif rsi > 55:
            rsi_signal = 'bullish'
        elif rsi < 45:
            rsi_signal = 'bearish'
        else:
            rsi_signal = 'neutral'
            
        # Check Stochastic RSI
        if stoch_rsi > 80:
            stoch_signal = 'overbought'
        elif stoch_rsi < 20:
            stoch_signal = 'oversold'
        elif stoch_rsi > 60:
            stoch_signal = 'bullish'
        elif stoch_rsi < 40:
            stoch_signal = 'bearish'
        else:
            stoch_signal = 'neutral'
            
        # Combine signals
        if rsi_signal in ['bullish', 'oversold'] and stoch_signal in ['bullish', 'oversold']:
            return 'bullish'
        elif rsi_signal in ['bearish', 'overbought'] and stoch_signal in ['bearish', 'overbought']:
            return 'bearish'
        else:
            return 'neutral'
    
    def analyze(self):
        """
        Analyze market context
        
        Returns:
            dict: Analysis results
        """
        if not self._fetch_data():
            return {
                'trend': 'unknown',
                'sentiment': 'unknown',
                'momentum': 'unknown',
                'pcr': 0,
                'vwiv': 0,
                'gex': 0,
                'rsi': 0,
                'stoch_rsi': 0,
                'success': False
            }
            
        self._calculate_indicators()
        
        trend = self._determine_trend()
        sentiment = self._determine_sentiment()
        momentum = self._determine_momentum()
        
        latest = self.data.iloc[-1]
        
        return {
            'trend': trend,
            'sentiment': sentiment,
            'momentum': momentum,
            'pcr': self.pcr,
            'vwiv': self.vwiv,
            'gex': self.gex,
            'rsi': latest['rsi'],
            'stoch_rsi': latest['stoch_rsi'],
            'ema10': latest['ema10'],
            'ema20': latest['ema20'],
            'ema50': latest['ema50'],
            'success': True
        }