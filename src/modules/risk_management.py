"""
Risk Management Module

This module handles position sizing, stop-loss calculation, and trade probability assessment.
"""

import logging
import math
import numpy as np

logger = logging.getLogger(__name__)

class RiskManager:
    """
    Manages trade risk through position sizing and stop-loss calculation
    
    Features:
    - Position sizing based on account risk
    - Stop-loss calculation methods
    - Trade probability assessment
    """
    
    def __init__(self, account_size, max_risk_percent=1.0):
        """
        Initialize the Risk Manager
        
        Args:
            account_size (float): Total trading account size
            max_risk_percent (float): Maximum risk per trade as percentage (default: 1%)
        """
        self.account_size = account_size
        self.max_risk_percent = max_risk_percent
        
    def calculate_position_size(self, entry_price, stop_loss_price, risk_amount=None):
        """
        Calculate position size based on risk parameters
        
        Args:
            entry_price (float): Entry price
            stop_loss_price (float): Stop-loss price
            risk_amount (float): Optional fixed risk amount
            
        Returns:
            dict: Position sizing results
        """
        if risk_amount is None:
            risk_amount = self.account_size * (self.max_risk_percent / 100)
            
        risk_per_share = abs(entry_price - stop_loss_price)
        if risk_per_share == 0:
            logger.warning("Zero risk per share - using minimum position size")
            risk_per_share = entry_price * 0.01  # 1% of entry price as fallback
            
        shares = math.floor(risk_amount / risk_per_share)
        position_value = shares * entry_price
        
        return {
            'shares': shares,
            'position_value': position_value,
            'risk_per_share': risk_per_share,
            'total_risk': risk_per_share * shares,
            'risk_percent': (risk_per_share * shares) / self.account_size * 100
        }
        
    def calculate_stop_loss(self, setup_type, entry_price, atr=None, support_resistance=None):
        """
        Calculate stop-loss price based on trade setup
        
        Args:
            setup_type (str): 'bullish', 'bearish', or 'neutral'
            entry_price (float): Entry price
            atr (float): Optional ATR value for volatility-based stops
            support_resistance (dict): Support/resistance levels
            
        Returns:
            float: Stop-loss price
        """
        if setup_type == 'bullish':
            if support_resistance and support_resistance.get('support'):
                # Use nearest support level with some buffer
                nearest_support = max(s for s in support_resistance['support'] if s < entry_price)
                return nearest_support * 0.99  # 1% below support
            elif atr:
                return entry_price - (atr * 1.5)
            else:
                return entry_price * 0.95  # 5% stop as fallback
                
        elif setup_type == 'bearish':
            if support_resistance and support_resistance.get('resistance'):
                # Use nearest resistance level with some buffer
                nearest_resistance = min(r for r in support_resistance['resistance'] if r > entry_price)
                return nearest_resistance * 1.01  # 1% above resistance
            elif atr:
                return entry_price + (atr * 1.5)
            else:
                return entry_price * 1.05  # 5% stop as fallback
                
        else:  # neutral
            if atr:
                return entry_price - (atr * 0.5)  # Tighter stop for neutral trades
            else:
                return entry_price * 0.98  # 2% stop for neutral trades
                
    def assess_trade_probability(self, setup_confidence, historical_success_rate=0.6):
        """
        Assess trade probability based on setup confidence
        
        Args:
            setup_confidence (float): Confidence score from trade setup (0-100)
            historical_success_rate (float): Historical success rate for this setup type
            
        Returns:
            float: Probability estimate (0-1)
        """
        # Blend confidence score with historical success rate
        confidence_weight = 0.7  # How much to weight the current setup confidence
        probability = (setup_confidence/100 * confidence_weight) + \
                     (historical_success_rate * (1 - confidence_weight))
                     
        return min(max(probability, 0), 1)  # Clamp between 0 and 1