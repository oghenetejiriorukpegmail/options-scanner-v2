"""
Data Caching Utility

Implements smart caching for market data with:
- Market hours awareness
- Rate limiting
- Automatic refresh logic
"""

import os
import json
import time
from datetime import datetime, time
import logging

logger = logging.getLogger(__name__)

class DataCache:
    def __init__(self, cache_dir='data_cache', max_fresh_fetches=3):
        """
        Initialize the data cache
        
        Args:
            cache_dir (str): Directory to store cache files
            max_fresh_fetches (int): Max fresh fetches per trading day
        """
        self.cache_dir = cache_dir
        self.max_fetches = max_fresh_fetches
        self.fetch_count = 0
        self.last_fetch_date = None
        
        os.makedirs(cache_dir, exist_ok=True)
        
    def is_market_open(self):
        """Check if markets are currently open (NYSE/NASDAQ hours)"""
        now = datetime.now().time()
        market_open = time(9, 30)  # 9:30 AM
        market_close = time(16, 0)  # 4:00 PM
        return market_open <= now <= market_close
        
    def should_fetch(self, cache_key):
        """
        Determine whether to fetch fresh data or use cache
        
        Args:
            cache_key (str): Unique identifier for the cached data
            
        Returns:
            bool: True if fresh data should be fetched
        """
        # Reset counter if it's a new trading day
        today = datetime.now().date()
        if self.last_fetch_date != today:
            self.fetch_count = 0
            self.last_fetch_date = today
            
        # Always use cache when market is closed
        if not self.is_market_open():
            return False
            
        # Check if we've hit the fetch limit
        if self.fetch_count >= self.max_fetches:
            return False
            
        # Check cache file freshness (max 1 hour during market hours)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        if os.path.exists(cache_file):
            mod_time = os.path.getmtime(cache_file)
            return (time.time() - mod_time) > 3600  # 1 hour
            
        return True
        
    def get_cache(self, cache_key):
        """Get data from cache if available"""
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading cache {cache_key}: {e}")
        return None
        
    def set_cache(self, cache_key, data):
        """Store data in cache"""
        self.fetch_count += 1
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Error writing cache {cache_key}: {e}")