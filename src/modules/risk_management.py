"""
Risk Management Module

This module offers risk control suggestions for trade setups.
"""

import logging
import numpy as np

logger = logging.getLogger(__name__)

class RiskManager:
    """
    Offers risk control suggestions
    
    Features:
    - Position Sizing
    - Stop Loss Recommendations
    """
    
    def __init__(self, symbol):
        """
        Initialize the Risk Manager
        
        Args:
            symbol (str): Stock symbol to analyze
        """
        self.symbol = symbol
    
    def _calculate_position_size(self, setup_results):
        """
        Calculate recommended position size based on volatility and setup
        
        Args:
            setup_results (dict): Trade setup results
            
        Returns:
            dict: Position size recommendations
        """
        # Get implied volatility
        iv = setup_results.get('vwiv', 0.3)  # Default to 30% if not available
        
        # Get GEX (Gamma Exposure)
        gex = setup_results.get('gex', 0)
        
        # Get setup confidence
        confidence = setup_results.get('confidence', 50)
        
        # Base position size (% of account)
        if iv < 0.3:  # Low IV
            base_size = 0.02  # 2% of account
        elif iv < 0.45:  # Moderate IV
            base_size = 0.015  # 1.5% of account
        elif iv < 0.6:  # High IV
            base_size = 0.01  # 1% of account
        else:  # Very high IV
            base_size = 0.005  # 0.5% of account
        
        # Adjust for GEX
        if abs(gex) > 1000:  # Extreme GEX
            gex_factor = 0.7  # Reduce position size by 30%
        elif abs(gex) > 500:  # High GEX
            gex_factor = 0.8  # Reduce position size by 20%
        else:
            gex_factor = 1.0  # No adjustment
        
        # Adjust for confidence
        confidence_factor = min(confidence / 100, 1.0)
        
        # Calculate final position size
        position_size = base_size * gex_factor * confidence_factor
        
        # Calculate alternative sizes
        conservative_size = position_size * 0.7
        aggressive_size = position_size * 1.3
        
        return {
            'recommended': position_size,
            'conservative': conservative_size,
            'aggressive': aggressive_size,
            'factors': {
                'iv': iv,
                'gex': gex,
                'confidence': confidence,
                'base_size': base_size,
                'gex_factor': gex_factor,
                'confidence_factor': confidence_factor
            }
        }
    
    def _calculate_stop_loss(self, setup_results, setup_type):
        """
        Calculate recommended stop loss levels
        
        Args:
            setup_results (dict): Trade setup results
            setup_type (str): Type of setup (bullish, bearish, neutral)
            
        Returns:
            dict: Stop loss recommendations
        """
        # Get current price
        current_price = setup_results.get('current_price', 0)
        if current_price == 0:
            return {
                'technical': 0,
                'percentage': 0,
                'factors': {
                    'current_price': 0
                }
            }
        
        # Get key levels
        support_levels = setup_results.get('support', [])
        resistance_levels = setup_results.get('resistance', [])
        ema10 = setup_results.get('ema10', 0)
        ema20 = setup_results.get('ema20', 0)
        
        # Get implied volatility
        iv = setup_results.get('vwiv', 0.3)  # Default to 30% if not available
        
        # Calculate percentage-based stop loss
        if iv < 0.3:  # Low IV
            percentage_stop = 0.02  # 2% stop loss
        elif iv < 0.45:  # Moderate IV
            percentage_stop = 0.03  # 3% stop loss
        elif iv < 0.6:  # High IV
            percentage_stop = 0.05  # 5% stop loss
        else:  # Very high IV
            percentage_stop = 0.07  # 7% stop loss
        
        # Calculate technical stop loss based on setup type
        if setup_type.startswith('bullish'):
            # For bullish setups, use support levels or EMAs
            if support_levels:
                technical_stop = support_levels[0] * 0.99  # Just below first support
            elif ema20 > 0:
                technical_stop = ema20 * 0.99  # Just below 20 EMA
            else:
                technical_stop = current_price * (1 - percentage_stop)
        elif setup_type.startswith('bearish'):
            # For bearish setups, use resistance levels or EMAs
            if resistance_levels:
                technical_stop = resistance_levels[0] * 1.01  # Just above first resistance
            elif ema20 > 0:
                technical_stop = ema20 * 1.01  # Just above 20 EMA
            else:
                technical_stop = current_price * (1 + percentage_stop)
        else:  # Neutral
            # For neutral setups, use a percentage-based stop
            technical_stop = current_price * (1 - percentage_stop)
        
        # Calculate percentage-based stop loss price
        percentage_stop_price = current_price * (1 - percentage_stop) if setup_type.startswith('bullish') else current_price * (1 + percentage_stop)
        
        return {
            'technical': technical_stop,
            'percentage': percentage_stop_price,
            'percentage_value': percentage_stop,
            'factors': {
                'current_price': current_price,
                'iv': iv,
                'support': support_levels[0] if support_levels else 0,
                'resistance': resistance_levels[0] if resistance_levels else 0,
                'ema10': ema10,
                'ema20': ema20
            }
        }
    
    def _calculate_risk_reward(self, setup_results, setup_type, stop_loss):
        """
        Calculate risk-reward ratio
        
        Args:
            setup_results (dict): Trade setup results
            setup_type (str): Type of setup (bullish, bearish, neutral)
            stop_loss (dict): Stop loss recommendations
            
        Returns:
            dict: Risk-reward calculations
        """
        # Get current price
        current_price = setup_results.get('current_price', 0)
        if current_price == 0:
            return {
                'ratio': 0,
                'reward': 0,
                'risk': 0
            }
        
        # Get key levels
        support_levels = setup_results.get('support', [])
        resistance_levels = setup_results.get('resistance', [])
        
        # Calculate risk (distance to stop loss)
        if setup_type.startswith('bullish'):
            risk = current_price - stop_loss['technical']
        elif setup_type.startswith('bearish'):
            risk = stop_loss['technical'] - current_price
        else:  # Neutral
            risk = abs(current_price - stop_loss['technical'])
        
        # Calculate reward (distance to target)
        if setup_type.startswith('bullish'):
            if resistance_levels:
                reward = resistance_levels[0] - current_price
            else:
                reward = current_price * 0.05  # Default 5% target
        elif setup_type.startswith('bearish'):
            if support_levels:
                reward = current_price - support_levels[0]
            else:
                reward = current_price * 0.05  # Default 5% target
        else:  # Neutral
            reward = current_price * 0.02  # Default 2% target for neutral setups
        
        # Calculate risk-reward ratio
        ratio = reward / risk if risk > 0 else 0
        
        return {
            'ratio': ratio,
            'reward': reward,
            'risk': risk,
            'target_price': current_price + reward if setup_type.startswith('bullish') else current_price - reward
        }
    
    def get_recommendations(self, setup_results):
        """
        Get risk management recommendations
        
        Args:
            setup_results (dict): Trade setup results
            
        Returns:
            dict: Risk management recommendations
        """
        setup_type = setup_results.get('setup', 'unknown')
        
        # Calculate position size
        position_size = self._calculate_position_size(setup_results)
        
        # Calculate stop loss
        stop_loss = self._calculate_stop_loss(setup_results, setup_type)
        
        # Calculate risk-reward ratio
        risk_reward = self._calculate_risk_reward(setup_results, setup_type, stop_loss)
        
        return {
            'position_size': position_size,
            'stop_loss': stop_loss,
            'risk_reward': risk_reward,
            'success': True
        }