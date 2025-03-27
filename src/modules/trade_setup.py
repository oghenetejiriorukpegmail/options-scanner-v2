"""
Trade Setup Rules Engine

This module defines conditions for trade setups based on market context and key levels.
"""

import logging
import numpy as np

logger = logging.getLogger(__name__)

class TradeSetupEngine:
    """
    Defines conditions for bullish, bearish, or neutral trade setups
    
    Features:
    - Bullish Setup Rules
    - Bearish Setup Rules
    - Neutral Setup Rules
    """
    
    def __init__(self, symbol):
        """
        Initialize the Trade Setup Rules Engine
        
        Args:
            symbol (str): Stock symbol to analyze
        """
        self.symbol = symbol
    
    def _evaluate_bullish_setup(self, context, levels):
        """
        Evaluate bullish setup conditions
        
        Args:
            context (dict): Market context analysis results
            levels (dict): Key levels mapping results
            
        Returns:
            tuple: (is_valid, confidence, reasons)
        """
        reasons = []
        points = 0
        max_points = 0
        
        # Check trend
        max_points += 3
        if context['trend'] == 'bullish':
            points += 3
            reasons.append("Strong bullish trend (EMA alignment)")
        elif context['trend'] == 'neutral':
            points += 1
            reasons.append("Neutral trend")
        
        # Check sentiment (PCR)
        max_points += 2
        if context['pcr'] < 0.8:
            points += 2
            reasons.append(f"Bullish sentiment (PCR: {context['pcr']:.2f})")
        elif context['pcr'] < 1.0:
            points += 1
            reasons.append(f"Neutral sentiment (PCR: {context['pcr']:.2f})")
        
        # Check momentum (RSI)
        max_points += 2
        if 55 <= context['rsi'] <= 80:
            points += 2
            reasons.append(f"Bullish momentum (RSI: {context['rsi']:.2f})")
        elif 45 <= context['rsi'] < 55:
            points += 1
            reasons.append(f"Neutral momentum (RSI: {context['rsi']:.2f})")
        
        # Check Stochastic RSI
        max_points += 2
        if context['stoch_rsi'] > 60:
            points += 2
            reasons.append(f"Bullish Stochastic RSI: {context['stoch_rsi']:.2f}")
        elif context['stoch_rsi'] > 40:
            points += 1
            reasons.append(f"Neutral Stochastic RSI: {context['stoch_rsi']:.2f}")
        
        # Check price relative to support levels
        max_points += 3
        if levels['support'] and levels['current_price'] <= levels['support'][0] * 1.02:
            points += 3
            reasons.append(f"Price near support ({levels['support'][0]:.2f})")
        elif levels['support'] and levels['current_price'] <= levels['support'][0] * 1.05:
            points += 1
            reasons.append(f"Price approaching support ({levels['support'][0]:.2f})")
        
        # Check GEX (simplified)
        max_points += 2
        if context.get('gex', 0) > 500:  # Positive GEX (> $500M)
            points += 2
            reasons.append("Positive GEX indicating bullish stability")
        
        # Calculate confidence score (0-100%)
        confidence = (points / max_points) * 100 if max_points > 0 else 0
        
        # Determine if setup is valid (confidence > 60%)
        is_valid = confidence > 60
        
        return is_valid, confidence, reasons
    
    def _evaluate_bearish_setup(self, context, levels):
        """
        Evaluate bearish setup conditions
        
        Args:
            context (dict): Market context analysis results
            levels (dict): Key levels mapping results
            
        Returns:
            tuple: (is_valid, confidence, reasons)
        """
        reasons = []
        points = 0
        max_points = 0
        
        # Check trend
        max_points += 3
        if context['trend'] == 'bearish':
            points += 3
            reasons.append("Strong bearish trend (EMA alignment)")
        elif context['trend'] == 'neutral':
            points += 1
            reasons.append("Neutral trend")
        
        # Check sentiment (PCR)
        max_points += 2
        if context['pcr'] > 1.2:
            points += 2
            reasons.append(f"Bearish sentiment (PCR: {context['pcr']:.2f})")
        elif context['pcr'] > 1.0:
            points += 1
            reasons.append(f"Neutral sentiment (PCR: {context['pcr']:.2f})")
        
        # Check momentum (RSI)
        max_points += 2
        if 20 <= context['rsi'] <= 45:
            points += 2
            reasons.append(f"Bearish momentum (RSI: {context['rsi']:.2f})")
        elif 45 < context['rsi'] <= 55:
            points += 1
            reasons.append(f"Neutral momentum (RSI: {context['rsi']:.2f})")
        
        # Check Stochastic RSI
        max_points += 2
        if context['stoch_rsi'] < 40:
            points += 2
            reasons.append(f"Bearish Stochastic RSI: {context['stoch_rsi']:.2f}")
        elif context['stoch_rsi'] < 60:
            points += 1
            reasons.append(f"Neutral Stochastic RSI: {context['stoch_rsi']:.2f}")
        
        # Check price relative to resistance levels
        max_points += 3
        if levels['resistance'] and levels['current_price'] >= levels['resistance'][0] * 0.98:
            points += 3
            reasons.append(f"Price near resistance ({levels['resistance'][0]:.2f})")
        elif levels['resistance'] and levels['current_price'] >= levels['resistance'][0] * 0.95:
            points += 1
            reasons.append(f"Price approaching resistance ({levels['resistance'][0]:.2f})")
        
        # Check GEX (simplified)
        max_points += 2
        if context.get('gex', 0) < -500:  # Negative GEX (< -$500M)
            points += 2
            reasons.append("Negative GEX indicating bearish pressure")
        
        # Calculate confidence score (0-100%)
        confidence = (points / max_points) * 100 if max_points > 0 else 0
        
        # Determine if setup is valid (confidence > 60%)
        is_valid = confidence > 60
        
        return is_valid, confidence, reasons
    
    def _evaluate_neutral_setup(self, context, levels):
        """
        Evaluate neutral setup conditions
        
        Args:
            context (dict): Market context analysis results
            levels (dict): Key levels mapping results
            
        Returns:
            tuple: (is_valid, confidence, reasons)
        """
        reasons = []
        points = 0
        max_points = 0
        
        # Check trend
        max_points += 3
        if context['trend'] == 'neutral':
            points += 3
            reasons.append("Neutral trend (flat EMAs)")
        
        # Check sentiment (PCR)
        max_points += 2
        if 0.8 <= context['pcr'] <= 1.2:
            points += 2
            reasons.append(f"Neutral sentiment (PCR: {context['pcr']:.2f})")
        
        # Check IV
        max_points += 2
        if context.get('vwiv', 0) < 0.4:  # IV < 40%
            points += 2
            reasons.append(f"Low implied volatility ({context.get('vwiv', 0):.2f})")
        elif context.get('vwiv', 0) < 0.5:
            points += 1
            reasons.append(f"Moderate implied volatility ({context.get('vwiv', 0):.2f})")
        
        # Check momentum (RSI)
        max_points += 2
        if 45 <= context['rsi'] <= 65:
            points += 2
            reasons.append(f"Neutral momentum (RSI: {context['rsi']:.2f})")
        
        # Check Stochastic RSI
        max_points += 2
        if 25 <= context['stoch_rsi'] <= 75:
            points += 2
            reasons.append(f"Neutral Stochastic RSI: {context['stoch_rsi']:.2f}")
        
        # Check price relative to Max Pain
        max_points += 3
        if levels['max_pain'] and abs(levels['current_price'] - levels['max_pain']) / levels['max_pain'] < 0.02:
            points += 3
            reasons.append(f"Price near Max Pain ({levels['max_pain']:.2f})")
        elif levels['max_pain'] and abs(levels['current_price'] - levels['max_pain']) / levels['max_pain'] < 0.05:
            points += 1
            reasons.append(f"Price approaching Max Pain ({levels['max_pain']:.2f})")
        
        # Check GEX (simplified)
        max_points += 2
        if abs(context.get('gex', 0)) < 200:  # GEX near zero (< $200M)
            points += 2
            reasons.append("GEX near zero indicating potential breakout")
        
        # Calculate confidence score (0-100%)
        confidence = (points / max_points) * 100 if max_points > 0 else 0
        
        # Determine if setup is valid (confidence > 60%)
        is_valid = confidence > 60
        
        return is_valid, confidence, reasons
    
    def determine_setup(self, context, levels):
        """
        Determine the most likely trade setup
        
        Args:
            context (dict): Market context analysis results
            levels (dict): Key levels mapping results
            
        Returns:
            dict: Trade setup results
        """
        # Evaluate each setup type
        bullish_valid, bullish_confidence, bullish_reasons = self._evaluate_bullish_setup(context, levels)
        bearish_valid, bearish_confidence, bearish_reasons = self._evaluate_bearish_setup(context, levels)
        neutral_valid, neutral_confidence, neutral_reasons = self._evaluate_neutral_setup(context, levels)
        
        # Determine the most likely setup
        setups = [
            ('bullish', bullish_confidence, bullish_valid, bullish_reasons),
            ('bearish', bearish_confidence, bearish_valid, bearish_reasons),
            ('neutral', neutral_confidence, neutral_valid, neutral_reasons)
        ]
        
        # Sort by confidence (highest first) and validity
        setups.sort(key=lambda x: (x[2], x[1]), reverse=True)
        
        # Get the most likely setup
        setup_type, confidence, is_valid, reasons = setups[0]
        
        # If no valid setup, use the highest confidence one but mark as low confidence
        if not is_valid:
            setup_type = f"weak_{setup_type}"
        
        return {
            'setup': setup_type,
            'confidence': confidence,
            'reasons': reasons,
            'all_setups': {
                'bullish': {'valid': bullish_valid, 'confidence': bullish_confidence, 'reasons': bullish_reasons},
                'bearish': {'valid': bearish_valid, 'confidence': bearish_confidence, 'reasons': bearish_reasons},
                'neutral': {'valid': neutral_valid, 'confidence': neutral_confidence, 'reasons': neutral_reasons}
            }
        }