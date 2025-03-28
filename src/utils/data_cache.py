"""
Data Caching Utility

Implements smart caching for market data with:
- Market hours awareness
- Rate limiting
- Automatic refresh logic
- Error handling and recovery
"""

import os
import json
import time as time_module
from datetime import datetime, time as datetime_time
import logging
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)

class DataCache:
    """
    A robust caching mechanism for financial data with market hours awareness.
    
    This class helps prevent excessive API calls by:
    1. Tracking market hours (only refresh during market hours)
    2. Limiting the number of fresh fetches per day
    3. Providing fallback to cached data when API limits are reached
    """
    
    def __init__(self, cache_dir: str = 'data_cache', max_fresh_fetches: int = 3):
        """
        Initialize the data cache
        
        Args:
            cache_dir: Directory to store cache files
            max_fresh_fetches: Maximum number of fresh fetches per trading day
        
        Raises:
            OSError: If the cache directory cannot be created
        """
        if not isinstance(cache_dir, str):
            raise TypeError("cache_dir must be a string")
        if not isinstance(max_fresh_fetches, int) or max_fresh_fetches < 1:
            raise ValueError("max_fresh_fetches must be a positive integer")
            
        self.cache_dir = cache_dir
        self.max_fetches = max_fresh_fetches
        self.fetch_count = 0
        self.last_fetch_date = None
        
        try:
            os.makedirs(cache_dir, exist_ok=True)
            logger.info(f"Cache directory initialized: {cache_dir}")
        except OSError as e:
            logger.error(f"Failed to create cache directory {cache_dir}: {e}")
            raise
        
    def is_market_open(self) -> bool:
        """
        Check if markets are currently open (NYSE/NASDAQ hours)
        
        Returns:
            bool: True if the market is currently open, False otherwise
            
        Note:
            This is a simplified check that doesn't account for weekends or holidays.
            For production systems, consider using a more comprehensive market calendar.
        """
        try:
            now = datetime.now().time()
            market_open = datetime_time(9, 30)  # 9:30 AM
            market_close = datetime_time(16, 0)  # 4:00 PM
            
            # Check if current time is within market hours
            is_open = market_open <= now <= market_close
            
            # Log market status for debugging
            if is_open:
                logger.debug("Market is currently open")
            else:
                logger.debug(f"Market is closed. Current time: {now}, Market hours: {market_open}-{market_close}")
                
            return is_open
            
        except Exception as e:
            logger.error(f"Error checking market hours: {e}")
            # Default to closed on error to prevent excessive API calls
            return False
        
    def should_fetch(self, cache_key: str) -> bool:
        """
        Determine whether to fetch fresh data or use cache
        
        This method implements a smart caching strategy that considers:
        1. Market hours (only refresh during market hours)
        2. Daily fetch limits to prevent API rate limiting
        3. Cache freshness (1 hour expiration during market hours)
        
        Args:
            cache_key: Unique identifier for the cached data
            
        Returns:
            bool: True if fresh data should be fetched, False if cache should be used
            
        Raises:
            TypeError: If cache_key is not a string
        """
        if not isinstance(cache_key, str):
            logger.error(f"Invalid cache key type: {type(cache_key)}")
            raise TypeError("cache_key must be a string")
            
        try:
            # Reset counter if it's a new trading day
            today = datetime.now().date()
            if self.last_fetch_date != today:
                logger.debug(f"New trading day detected. Resetting fetch counter.")
                self.fetch_count = 0
                self.last_fetch_date = today
                
            # Always use cache when market is closed
            if not self.is_market_open():
                logger.debug(f"Market is closed. Using cached data for {cache_key}")
                return False
                
            # Check if we've hit the fetch limit
            if self.fetch_count >= self.max_fetches:
                logger.debug(f"Daily fetch limit reached ({self.max_fetches}). Using cached data for {cache_key}")
                return False
                
            # Check cache file freshness (max 1 hour during market hours)
            cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
            if os.path.exists(cache_file):
                try:
                    mod_time = os.path.getmtime(cache_file)
                    cache_age = time_module.time() - mod_time
                    should_refresh = cache_age > 3600  # 1 hour
                    
                    if should_refresh:
                        logger.debug(f"Cache for {cache_key} is stale ({cache_age:.1f} seconds old). Refreshing.")
                    else:
                        logger.debug(f"Cache for {cache_key} is fresh ({cache_age:.1f} seconds old). Using cached data.")
                        
                    return should_refresh
                except OSError as e:
                    logger.warning(f"Error checking cache file timestamp for {cache_key}: {e}")
                    # If we can't check the timestamp, assume we need fresh data
                    return True
            
            logger.debug(f"No cache exists for {cache_key}. Fetching fresh data.")
            return True
            
        except Exception as e:
            logger.error(f"Unexpected error in should_fetch for {cache_key}: {e}")
            # On error, default to using cache to prevent excessive API calls
            return False
        
    def get_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Get data from cache if available
        
        Args:
            cache_key: Unique identifier for the cached data
            
        Returns:
            Optional[Dict[str, Any]]: The cached data if available, None otherwise
            
        Raises:
            TypeError: If cache_key is not a string
        """
        if not isinstance(cache_key, str):
            logger.error(f"Invalid cache key type: {type(cache_key)}")
            raise TypeError("cache_key must be a string")
            
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        
        if not os.path.exists(cache_file):
            logger.debug(f"Cache file not found for {cache_key}")
            return None
            
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
                logger.debug(f"Successfully loaded cache for {cache_key}")
                return data
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error reading cache {cache_key}: {e}")
            # If the file is corrupted, remove it
            try:
                os.remove(cache_file)
                logger.warning(f"Removed corrupted cache file for {cache_key}")
            except OSError:
                pass
            return None
        except OSError as e:
            logger.error(f"File I/O error reading cache {cache_key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading cache {cache_key}: {e}")
            return None
        
    def set_cache(self, cache_key: str, data: Any) -> bool:
        """
        Store data in cache
        
        Args:
            cache_key: Unique identifier for the cached data
            data: The data to cache (will be converted to JSON-serializable format)
            
        Returns:
            bool: True if the data was successfully cached, False otherwise
            
        Raises:
            TypeError: If cache_key is not a string
        """
        if not isinstance(cache_key, str):
            logger.error(f"Invalid cache key type: {type(cache_key)}")
            raise TypeError("cache_key must be a string")
            
        if data is None:
            logger.warning(f"Attempted to cache None data for {cache_key}")
            return False
            
        self.fetch_count += 1
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        
        try:
            # Convert data to JSON-serializable format
            serializable_data = self._make_json_serializable(data)
            
            # Create a temporary file first to avoid partial writes
            temp_file = f"{cache_file}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(serializable_data, f)
                
            # Rename the temporary file to the actual cache file (atomic operation)
            os.replace(temp_file, cache_file)
            
            logger.debug(f"Successfully cached data for {cache_key}")
            return True
            
        except (TypeError, ValueError) as e:
            logger.error(f"JSON serialization error for {cache_key}: {e}")
            return False
        except OSError as e:
            logger.error(f"File I/O error writing cache {cache_key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error writing cache {cache_key}: {e}")
            return False
            
    def _make_json_serializable(self, obj: Any) -> Any:
        """
        Convert objects to JSON-serializable format
        
        This method recursively converts complex objects to JSON-serializable types:
        - Dictionaries: Process each key-value pair
        - Lists: Process each item
        - Datetime objects: Convert to ISO format string
        - Pandas objects: Convert to dictionaries then process
        - NumPy arrays: Convert to lists
        - Pandas Timestamps: Convert to strings
        
        Args:
            obj: The object to convert
            
        Returns:
            Any: A JSON-serializable version of the input object
        """
        try:
            if isinstance(obj, dict):
                return {k: self._make_json_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [self._make_json_serializable(item) for item in obj]
            elif hasattr(obj, 'isoformat'):  # Handle datetime objects
                return obj.isoformat()
            elif hasattr(obj, 'to_dict'):  # Handle pandas objects
                return self._make_json_serializable(obj.to_dict())
            elif hasattr(obj, 'tolist'):  # Handle numpy arrays
                return obj.tolist()
            elif str(type(obj)) == "<class 'pandas._libs.tslibs.timestamps.Timestamp'>":
                # Handle pandas Timestamp objects
                return str(obj)
            else:
                # Check if object is a basic JSON type (str, int, float, bool, None)
                if isinstance(obj, (str, int, float, bool, type(None))):
                    return obj
                # For other types, try to convert to string
                return str(obj)
        except Exception as e:
            logger.error(f"Error converting object to JSON-serializable format: {e}")
            # Return a safe default value
            return str(obj)