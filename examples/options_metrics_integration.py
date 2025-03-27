#!/usr/bin/env python3
"""
Options Metrics Integration Example

This example demonstrates how to integrate the OptionsMetricsAnalyzer
with the existing scanner module to enhance trading decisions.
"""

import sys
import os
import json
from datetime import datetime

# Add the project root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.modules.scanner import StockScanner
from src.modules.options_metrics import OptionsMetricsAnalyzer
from src.utils.data_cache import DataCache

def enhance_scan_results_with_options_metrics(scan_results):
    """
    Enhance scan results with advanced options metrics
    
    Args:
        scan_results (list): Original scan results from StockScanner
        
    Returns:
        list: Enhanced scan results with options metrics
    """
    # Create a shared cache instance
    cache = DataCache()
    
    enhanced_results = []
    
    for result in scan_results:
        symbol = result['symbol']
        print(f"Enhancing scan results for {symbol} with advanced options metrics...")
        
        # Initialize options metrics analyzer
        analyzer = OptionsMetricsAnalyzer(symbol, cache=cache)
        
        try:
            # Calculate options metrics
            metrics = analyzer.calculate_metrics()
            
            if metrics:
                # Add options metrics to the result
                result['options_metrics'] = {
                    'high_gamma_strikes': metrics['high_gamma_strikes'],
                    'gex': {
                        'total_gex': metrics['gex']['total_gex'],
                        'gex_direction': metrics['gex']['gex_direction']
                    },
                    'vwiv': metrics['vwiv']['vwiv']
                }
                
                # Adjust confidence based on options metrics
                if metrics['gex']['gex_direction'] == 'positive' and result['setup'] == 'bullish_setup':
                    # Increase confidence for bullish setup with positive GEX
                    result['confidence'] = min(100, result['confidence'] * 1.1)
                    result['reasons'].append("Positive GEX confirms bullish bias")
                    
                elif metrics['gex']['gex_direction'] == 'negative' and result['setup'] == 'bearish_setup':
                    # Increase confidence for bearish setup with negative GEX
                    result['confidence'] = min(100, result['confidence'] * 1.1)
                    result['reasons'].append("Negative GEX confirms bearish bias")
                
                # Check if current price is near high gamma strike
                current_price = result['current_price']
                for strike in metrics['high_gamma_strikes']:
                    if abs(strike - current_price) / current_price < 0.02:  # Within 2%
                        result['reasons'].append(f"Price near high gamma strike at ${strike:.2f}")
                        break
                
                print(f"Successfully enhanced {symbol} with options metrics")
            else:
                print(f"Could not calculate options metrics for {symbol}")
                
        except Exception as e:
            print(f"Error enhancing {symbol} with options metrics: {e}")
            
        enhanced_results.append(result)
    
    return enhanced_results

def apply_advanced_filters(results, config):
    """
    Apply advanced filters based on options metrics
    
    Args:
        results (list): Scan results with options metrics
        config (dict): Configuration with filter settings
        
    Returns:
        list: Filtered results
    """
    filters = config['filters']
    filtered_results = []
    
    for result in results:
        # Skip results without options metrics
        if 'options_metrics' not in result:
            continue
            
        # Apply gamma min filter
        if 'gamma_min' in filters and result['options_metrics']['high_gamma_strikes']:
            if len(result['options_metrics']['high_gamma_strikes']) < filters.get('high_gamma_count_min', 0):
                continue
                
        # Apply GEX direction filter
        if 'gex_direction' in filters and isinstance(filters['gex_direction'], list):
            if result['options_metrics']['gex']['gex_direction'] not in filters['gex_direction']:
                continue
                
        # Apply VWIV percentile filter
        if 'vwiv_percentile_min' in filters and 'vwiv_percentile_max' in filters:
            vwiv = result['options_metrics'].get('vwiv', 0)
            if not (filters['vwiv_percentile_min'] <= vwiv <= filters['vwiv_percentile_max']):
                continue
                
        filtered_results.append(result)
    
    return filtered_results

def main():
    """Main function to demonstrate options metrics integration"""
    # Load configuration
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # Run scanner
    print("Running stock scanner...")
    scanner = StockScanner(config_file='config.json')
    scan_results = scanner.scan()
    
    if not scan_results:
        print("No scan results found")
        return
        
    print(f"Found {len(scan_results)} initial scan results")
    
    # Enhance results with options metrics
    if config.get('options_metrics', {}).get('enabled', False):
        print("Enhancing results with options metrics...")
        enhanced_results = enhance_scan_results_with_options_metrics(scan_results)
        
        # Apply advanced filters
        print("Applying advanced filters...")
        filtered_results = apply_advanced_filters(enhanced_results, config)
        
        print(f"Final results after advanced filtering: {len(filtered_results)}")
        
        # Display results
        print("\n=== Final Scan Results with Options Metrics ===")
        print(f"{'Symbol':<6} {'Setup':<15} {'Confidence':>10} {'GEX Direction':>15} {'High Gamma Strikes':>20}")
        print("-" * 70)
        
        for result in filtered_results:
            high_gamma_count = len(result['options_metrics']['high_gamma_strikes']) if 'options_metrics' in result else 0
            gex_direction = result['options_metrics']['gex']['gex_direction'] if 'options_metrics' in result else 'N/A'
            
            print(f"{result['symbol']:<6} {result['setup']:<15} {result['confidence']:>9.1f}% "
                  f"{gex_direction:>15} {high_gamma_count:>20}")
        
        # Save enhanced results
        output_file = f"enhanced_scan_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_path = os.path.join(config['output_dir'], output_file)
        
        os.makedirs(config['output_dir'], exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(filtered_results, f, indent=2, default=str)
            
        print(f"\nEnhanced results saved to {output_path}")
    else:
        print("Options metrics enhancement is disabled in config")

if __name__ == "__main__":
    main()