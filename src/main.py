#!/usr/bin/env python3
"""
Options-Technical Hybrid Scanner
Main entry point for the application
"""

import os
import sys
import logging
import argparse
from datetime import datetime

# Add the src directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import modules
from src.modules.market_context import MarketContextAnalyzer
from src.modules.key_levels import KeyLevelsMapper
from src.modules.trade_setup import TradeSetupEngine
from src.modules.confirmation import ConfirmationModule
from src.modules.risk_management import RiskManager
from src.modules.scanner import StockScanner
from src.web.app import create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"scanner_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Options-Technical Hybrid Scanner')
    parser.add_argument('--web', action='store_true', help='Start the web interface')
    parser.add_argument('--scan', action='store_true', help='Run the scanner')
    parser.add_argument('--symbol', type=str, help='Symbol to analyze')
    parser.add_argument('--config', type=str, default='config.json', help='Configuration file')
    return parser.parse_args()

def main():
    """Main entry point"""
    args = parse_arguments()
    logger.info("Starting Options-Technical Hybrid Scanner")
    
    if args.web:
        # Start the web interface
        app = create_app()
        app.run(debug=True, host='0.0.0.0', port=8080)
    elif args.scan:
        # Run the scanner
        scanner = StockScanner()
        results = scanner.scan()
        for result in results:
            print(f"Symbol: {result['symbol']}, Setup: {result['setup']}, Confidence: {result['confidence']}%")
    elif args.symbol:
        # Analyze a specific symbol
        symbol = args.symbol.upper()
        logger.info(f"Analyzing {symbol}")
        
        # Initialize modules
        market_context = MarketContextAnalyzer(symbol)
        key_levels = KeyLevelsMapper(symbol)
        trade_setup = TradeSetupEngine(symbol)
        confirmation = ConfirmationModule(symbol)
        risk_manager = RiskManager(symbol)
        
        # Analyze market context
        context_results = market_context.analyze()
        print(f"\n=== Market Context for {symbol} ===")
        print(f"Trend: {context_results['trend']}")
        print(f"Sentiment: {context_results['sentiment']}")
        print(f"Momentum: {context_results['momentum']}")
        
        # Map key levels
        levels_results = key_levels.map_levels()
        print(f"\n=== Key Levels for {symbol} ===")
        print(f"Support Levels: {levels_results['support']}")
        print(f"Resistance Levels: {levels_results['resistance']}")
        print(f"Max Pain: {levels_results['max_pain']}")
        
        # Determine trade setup
        setup_results = trade_setup.determine_setup(context_results, levels_results)
        print(f"\n=== Trade Setup for {symbol} ===")
        print(f"Setup: {setup_results['setup']}")
        print(f"Confidence: {setup_results['confidence']}")
        
        # Get confirmation signals
        confirmation_results = confirmation.get_signals(setup_results)
        print(f"\n=== Confirmation Signals for {symbol} ===")
        print(f"Entry Signal: {confirmation_results['entry']}")
        print(f"Exit Signal: {confirmation_results['exit']}")
        
        # Get risk management recommendations
        risk_results = risk_manager.get_recommendations(setup_results)
        print(f"\n=== Risk Management for {symbol} ===")
        print(f"Position Size: {risk_results['position_size']}")
        print(f"Stop Loss: {risk_results['stop_loss']}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()