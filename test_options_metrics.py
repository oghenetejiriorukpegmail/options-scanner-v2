#!/usr/bin/env python3
"""
Test script for Options Metrics Module

This script contains unit tests for the OptionsMetricsAnalyzer class
and demonstrates how to use it to calculate advanced options metrics.
"""

import sys
import os
import json
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

# Add the project root directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.modules.options_metrics import OptionsMetricsAnalyzer

class TestOptionsMetrics(unittest.TestCase):
    """Unit tests for OptionsMetricsAnalyzer class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.symbol = 'TSLA'
        self.analyzer = OptionsMetricsAnalyzer(self.symbol)
        
        # Mock options chain data
        self.mock_chain = {
            'symbol': self.symbol,
            'expiration': '2025-04-15',
            'current_price': 180.50,
            'timestamp': datetime.now().isoformat(),
            'calls': [
                {'strike': 175, 'delta': 0.65, 'gamma': 0.12, 'theta': -0.05, 'vega': 0.35, 'impliedVolatility': 0.45, 'volume': 1000, 'openInterest': 500},
                {'strike': 180, 'delta': 0.55, 'gamma': 0.15, 'theta': -0.06, 'vega': 0.40, 'impliedVolatility': 0.42, 'volume': 1500, 'openInterest': 600}
            ],
            'puts': [
                {'strike': 175, 'delta': -0.35, 'gamma': 0.10, 'theta': -0.04, 'vega': 0.30, 'impliedVolatility': 0.48, 'volume': 800, 'openInterest': 400},
                {'strike': 180, 'delta': -0.45, 'gamma': 0.13, 'theta': -0.05, 'vega': 0.35, 'impliedVolatility': 0.44, 'volume': 1200, 'openInterest': 500}
            ]
        }
    
    def test_calculate_charm(self):
        """Test charm calculation"""
        charm = self.analyzer.calculate_charm(self.mock_chain)
        self.assertIsInstance(charm, list)
        self.assertEqual(len(charm), 2)  # Should have data for both strikes
        for strike_data in charm:
            self.assertIn('strike', strike_data)
            self.assertIn('total_charm', strike_data)
            self.assertIn('call_charm', strike_data)
            self.assertIn('put_charm', strike_data)
    
    def test_calculate_vanna(self):
        """Test vanna calculation"""
        vanna = self.analyzer.calculate_vanna(self.mock_chain)
        self.assertIsInstance(vanna, list)
        self.assertEqual(len(vanna), 2)
        for strike_data in vanna:
            self.assertIn('strike', strike_data)
            self.assertIn('total_vanna', strike_data)
            self.assertIn('call_vanna', strike_data)
            self.assertIn('put_vanna', strike_data)
    
    def test_calculate_vomma(self):
        """Test vomma calculation"""
        vomma = self.analyzer.calculate_vomma(self.mock_chain)
        self.assertIsInstance(vomma, list)
        self.assertEqual(len(vomma), 2)
        for strike_data in vomma:
            self.assertIn('strike', strike_data)
            self.assertIn('total_vomma', strike_data)
            self.assertIn('call_vomma', strike_data)
            self.assertIn('put_vomma', strike_data)
    
    def test_calculate_metrics_includes_second_order_greeks(self):
        """Test that calculate_metrics includes second-order Greeks"""
        metrics = self.analyzer.calculate_metrics()
        self.assertIn('charm', metrics)
        self.assertIn('vanna', metrics)
        self.assertIn('vomma', metrics)
        self.assertIsInstance(metrics['charm'], list)
        self.assertIsInstance(metrics['vanna'], list)
        self.assertIsInstance(metrics['vomma'], list)

def demo_usage():
    """Demonstrate usage of the OptionsMetricsAnalyzer"""
    import argparse
    parser = argparse.ArgumentParser(description='Test Options Metrics')
    parser.add_argument('--symbol', type=str, default='TSLA', help='Symbol to analyze')
    parser.add_argument('--expiration', type=str, help='Expiration date (YYYY-MM-DD)')
    args = parser.parse_args()
    
    symbol = args.symbol.upper()
    expiration = args.expiration
    
    print(f"Analyzing options metrics for {symbol}")
    
    analyzer = OptionsMetricsAnalyzer(symbol)
    current_price = analyzer.get_current_price()
    print(f"Current price: ${current_price:.2f}")
    
    print(f"Fetching options chain for {symbol}...")
    options_chain = analyzer.get_options_chain(expiration)
    if not options_chain:
        print(f"Error: Could not get options chain for {symbol}")
        return
        
    print(f"Calculating advanced options metrics...")
    metrics = analyzer.calculate_metrics(expiration)
    if not metrics:
        print(f"Error: Could not calculate metrics for {symbol}")
        return
    
    # Display key metrics including second-order Greeks
    print("\n=== Key Options Metrics ===")
    print(f"Symbol: {metrics['symbol']}")
    print(f"Current Price: ${metrics['current_price']:.2f}")
    print(f"Expiration: {metrics['expiration']}")
    
    print("\n=== Second-Order Greeks ===")
    print(f"Charm values calculated for {len(metrics['charm'])} strikes")
    print(f"Vanna values calculated for {len(metrics['vanna'])} strikes")
    print(f"Vomma values calculated for {len(metrics['vomma'])} strikes")
    
    # Save metrics to file
    output_file = f"{symbol}_options_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(metrics, f, indent=2, default=str)
    print(f"\nMetrics saved to {output_file}")

if __name__ == "__main__":
    # Run unit tests
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
    
    # Then run demo usage
    demo_usage()