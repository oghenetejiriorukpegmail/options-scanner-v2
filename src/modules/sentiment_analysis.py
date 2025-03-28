"""
Sentiment Analysis Module

This module analyzes social media sentiment for stocks from various sources.
"""

import logging
import json # Added import
import os # Added import
import tweepy # Added import
import praw # Added import
import requests # Added requests import
from datetime import datetime, timedelta # Added datetime imports
from src.utils.data_cache import DataCache
from textblob import TextBlob # Added import
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer # Added VADER

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    """
    Analyzes social media sentiment for stocks.

    Sources:
    - Twitter/X (Planned)
    - Reddit (r/wallstreetbets, r/options, etc.) (Planned)
    - StockTwits (Planned)
    """

    def __init__(self, symbol, cache=None):
        """
        Initialize the Sentiment Analyzer.

        Args:
            symbol (str): Stock symbol.
            cache (DataCache, optional): Cache instance. Defaults to a new DataCache instance.
        """
        self.symbol = symbol.upper()
        self.cache = cache or DataCache()
        self.config = self._load_config()
        sentiment_config = self.config.get('sentiment_analysis', {})
        self.api_keys = {
            'twitter_key': sentiment_config.get('twitter_api_key'),
            'twitter_secret': sentiment_config.get('twitter_api_secret'),
            'twitter_bearer': sentiment_config.get('twitter_bearer_token'),
            'reddit': sentiment_config.get('reddit_api_key'), # Expects dict: client_id, client_secret, user_agent
            'stocktwits_token': sentiment_config.get('stocktwits_access_token') # Changed key name
        }
        self.enabled_sources = sentiment_config.get('sources', [])
        self.vader_analyzer = SentimentIntensityAnalyzer() # Instantiate VADER

    def _load_config(self, config_file='config.json'):
        """Load sentiment analysis configuration"""
        default_config = {
            "sentiment_analysis": {
                "enabled": False,
                "sources": ["twitter", "reddit", "stocktwits"],
                "lookback_days": 7,
                "min_sentiment_score": 0.5,
                "twitter_api_key": None,
                "reddit_api_key": None,
                "stocktwits_api_key": None
            }
        }
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    user_config = json.load(f)
                    # Merge only the sentiment_analysis part
                    if 'sentiment_analysis' in user_config:
                         default_config['sentiment_analysis'].update(user_config['sentiment_analysis'])
            else:
                logger.warning(f"Config file {config_file} not found, using default sentiment config.")
        except Exception as e:
            logger.error(f"Error loading sentiment config from {config_file}: {e}")
        
        return default_config # Return the whole structure for consistency, though only sentiment part is used here

    def analyze_sentiment(self):
        """
        Analyze overall sentiment across all configured platforms.

        Returns:
            dict: Aggregated sentiment data including score and trend.
                  Returns None if analysis fails.
        """
        logger.info(f"Analyzing sentiment for {self.symbol}")
        
        scores = {}
        total_score = 0
        valid_sources_count = 0

        if 'twitter' in self.enabled_sources:
            twitter_data = self.get_twitter_sentiment()
            if twitter_data and twitter_data.get('score') is not None:
                scores['twitter'] = twitter_data['score']
                total_score += twitter_data['score']
                valid_sources_count += 1
            else:
                scores['twitter'] = None
        else:
             scores['twitter'] = None

        if 'reddit' in self.enabled_sources:
            reddit_data = self.get_reddit_sentiment()
            if reddit_data and reddit_data.get('score') is not None:
                scores['reddit'] = reddit_data['score']
                total_score += reddit_data['score']
                valid_sources_count += 1
            else:
                scores['reddit'] = None
        else:
            scores['reddit'] = None

        if 'stocktwits' in self.enabled_sources:
            stocktwits_data = self.get_stocktwits_sentiment()
            if stocktwits_data and stocktwits_data.get('score') is not None:
                scores['stocktwits'] = stocktwits_data['score']
                total_score += stocktwits_data['score']
                valid_sources_count += 1
            else:
                scores['stocktwits'] = None
        else:
            scores['stocktwits'] = None

        overall_score = total_score / valid_sources_count if valid_sources_count > 0 else None

        # TODO: Implement trend calculation based on historical data
        trend_data = self.get_sentiment_trends()
        trend = trend_data['trend'] if trend_data else 'stable' # Placeholder

        sentiment_data = {
            'overall_score': overall_score,
            'twitter_score': scores['twitter'],
            'reddit_score': scores['reddit'],
            'stocktwits_score': scores['stocktwits'],
            'trend': trend
        }

        # Save historical data point if score is valid
        if overall_score is not None:
            self._save_historical_sentiment(overall_score)
        
        logger.debug(f"Sentiment analysis result for {self.symbol}: {sentiment_data}")
        return sentiment_data

    def _save_historical_sentiment(self, score):
        """Saves the current sentiment score to a daily historical file."""
        history_dir = os.path.join(self.cache.cache_dir, 'sentiment_history')
        os.makedirs(history_dir, exist_ok=True)
        
        today_str = datetime.now().strftime('%Y%m%d')
        file_path = os.path.join(history_dir, f"{self.symbol}_{today_str}.json")
        
        new_entry = {
            'timestamp': datetime.now().isoformat(),
            'score': score
        }
        
        history = []
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    history = json.load(f)
                    # Ensure it's a list
                    if not isinstance(history, list):
                        logger.warning(f"Corrupted history file {file_path}, resetting.")
                        history = []
        except json.JSONDecodeError:
            logger.warning(f"Could not decode JSON from {file_path}, resetting.")
            history = []
        except Exception as e:
            logger.error(f"Error reading sentiment history file {file_path}: {e}")
            # Don't proceed if we can't read the file reliably
            return

        history.append(new_entry)
        
        try:
            with open(file_path, 'w') as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            logger.error(f"Error writing sentiment history file {file_path}: {e}")

    def get_twitter_sentiment(self):
        """
        Get sentiment from Twitter/X.

        Returns:
            dict: Sentiment score and related data from Twitter.
                  Returns None if fetching or analysis fails.
        """
        cache_key = f"sentiment_twitter_{self.symbol}"
        # Check cache first
        if not self.cache.should_fetch(cache_key):
             cached_data = self.cache.get_cache(cache_key)
             if cached_data:
                 logger.debug(f"Using cached Twitter sentiment for {self.symbol}")
                 return cached_data

        logger.debug(f"Fetching Twitter sentiment for {self.symbol}")

        # Use API Key and Secret for v1.1 authentication
        consumer_key = self.config.get('sentiment_analysis', {}).get('twitter_api_key')
        consumer_secret = self.config.get('sentiment_analysis', {}).get('twitter_api_secret')

        if not consumer_key or not consumer_secret:
            logger.warning("Twitter API Key or Secret not configured. Skipping Twitter sentiment.")
            return None

        try:
            # Initialize Tweepy API v1.1 client
            auth = tweepy.OAuth1UserHandler(consumer_key, consumer_secret)
            # If you have Access Token and Secret, add them here:
            # auth.set_access_token(access_token, access_token_secret)
            api = tweepy.API(auth, wait_on_rate_limit=True) # wait_on_rate_limit handles rate limits gracefully

            # Construct query for v1.1 standard search
            # Note: v1.1 standard search has limitations (e.g., only last 7 days)
            query = f"${self.symbol} OR #{self.symbol} -filter:retweets lang:en"
            
            # Fetch tweets using v1.1 search
            # Use tweet_mode='extended' to get full text
            search_results = api.search_tweets(q=query, count=100, result_type='recent', tweet_mode='extended')

            tweets = search_results
            if not tweets:
                logger.info(f"No recent tweets found for query: {query}")
                empty_result = {'score': None, 'polarity': None, 'analyzed_count': 0}
                self.cache.set_cache(cache_key, empty_result)
                return empty_result

        except tweepy.errors.TweepyException as e:
            logger.error(f"Tweepy API error fetching tweets for {self.symbol}: {e}")
            # Specific handling for authentication errors if needed
            if "authentication credentials" in str(e).lower():
                 logger.error("Check Twitter API Key/Secret/Tokens in config.json")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching tweets for {self.symbol}: {e}")
            return None

        total_polarity = 0
        analyzed_count = 0

        for tweet in tweets:
            try:
                # Get full text from extended mode
                tweet_text = tweet.full_text if hasattr(tweet, 'full_text') else tweet.text
                # Basic cleaning
                cleaned_text = ' '.join(tweet_text.split())
                # Use VADER for sentiment scoring
                vs = self.vader_analyzer.polarity_scores(cleaned_text)
                total_polarity += vs['compound'] # Use VADER's compound score
                analyzed_count += 1
            except Exception as e:
                logger.error(f"Error analyzing tweet ID {tweet.id}: '{tweet_text}'. Error: {e}")

        if analyzed_count == 0:
            logger.warning(f"Could not analyze any fetched tweets for {self.symbol}")
            empty_result = {'score': None, 'polarity': None, 'analyzed_count': 0}
            self.cache.set_cache(cache_key, empty_result)
            return empty_result

        average_polarity = total_polarity / analyzed_count

        # Convert polarity (-1 to 1) to a score (0 to 1)
        sentiment_score = (average_polarity + 1) / 2

        result = {
            'score': sentiment_score,
            'polarity': average_polarity,
            'analyzed_count': analyzed_count
        }
        
        # Save to cache before returning
        self.cache.set_cache(cache_key, result)

        return result

    def get_reddit_sentiment(self):
        """
        Get sentiment from relevant Reddit subreddits.

        Returns:
            dict: Sentiment score and related data from Reddit.
                  Returns None if fetching or analysis fails.
        """
        cache_key = f"sentiment_reddit_{self.symbol}"
        # Check cache first
        if not self.cache.should_fetch(cache_key):
             cached_data = self.cache.get_cache(cache_key)
             if cached_data:
                 logger.debug(f"Using cached Reddit sentiment for {self.symbol}")
                 return cached_data

        logger.debug(f"Fetching Reddit sentiment for {self.symbol}")

        api_config = self.api_keys.get('reddit')
        if not api_config or not all(k in api_config for k in ['client_id', 'client_secret', 'user_agent']):
            logger.warning("Reddit API keys (client_id, client_secret, user_agent) not fully configured. Skipping Reddit sentiment.")
            return None

        try:
            reddit = praw.Reddit(
                client_id=api_config['client_id'],
                client_secret=api_config['client_secret'],
                user_agent=api_config['user_agent'],
                read_only=True # Read-only mode is sufficient
            )

            subreddits_to_check = ['wallstreetbets', 'options', 'stocks', 'investing', 'StockMarket']
            relevant_titles = []
            search_limit_per_subreddit = 25 # Limit API calls

            for sub_name in subreddits_to_check:
                try:
                    subreddit = reddit.subreddit(sub_name)
                    # Fetch recent hot submissions
                    for submission in subreddit.hot(limit=search_limit_per_subreddit):
                        # Check if symbol is mentioned in the title (case-insensitive)
                        if self.symbol.lower() in submission.title.lower():
                            relevant_titles.append(submission.title)
                except Exception as e:
                    logger.warning(f"Could not fetch from subreddit r/{sub_name}: {e}")
                    continue # Continue to the next subreddit

            if not relevant_titles:
                logger.info(f"No recent Reddit submissions found mentioning {self.symbol} in checked subreddits.")
                empty_result = {'score': None, 'polarity': None, 'analyzed_count': 0}
                self.cache.set_cache(cache_key, empty_result)
                return empty_result

        except praw.exceptions.PrawcoreException as e:
            logger.error(f"PRAW API error fetching Reddit data for {self.symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching Reddit data for {self.symbol}: {e}")
            return None

        total_polarity = 0
        analyzed_count = 0

        for title in relevant_titles:
            try:
                # Use VADER for sentiment scoring
                vs = self.vader_analyzer.polarity_scores(title)
                total_polarity += vs['compound'] # Use VADER's compound score
                analyzed_count += 1
            except Exception as e:
                logger.error(f"Error analyzing Reddit title: '{title}'. Error: {e}")

        if analyzed_count == 0:
            logger.warning(f"Could not analyze any fetched Reddit titles for {self.symbol}")
            empty_result = {'score': None, 'polarity': None, 'analyzed_count': 0}
            self.cache.set_cache(cache_key, empty_result)
            return empty_result

        average_polarity = total_polarity / analyzed_count

        # Convert polarity (-1 to 1) to a score (0 to 1)
        sentiment_score = (average_polarity + 1) / 2

        result = {
            'score': sentiment_score,
            'polarity': average_polarity,
            'analyzed_count': analyzed_count
        }

        # Save to cache before returning
        self.cache.set_cache(cache_key, result)

        return result

    def get_stocktwits_sentiment(self):
        """
        Get sentiment from StockTwits.

        Returns:
            dict: Sentiment score and related data from StockTwits.
                  Returns None if fetching or analysis fails.
        """
        cache_key = f"sentiment_stocktwits_{self.symbol}"
        # Check cache first
        if not self.cache.should_fetch(cache_key):
             cached_data = self.cache.get_cache(cache_key)
             if cached_data:
                 logger.debug(f"Using cached StockTwits sentiment for {self.symbol}")
                 return cached_data

        logger.debug(f"Fetching StockTwits sentiment for {self.symbol}")

        # Use requests library to fetch directly from StockTwits API v2
        api_url = f"https://api.stocktwits.com/api/2/streams/symbol/{self.symbol}.json"
        
        # Check for access token and add it to params if available
        access_token = self.api_keys.get('stocktwits_token')
        if not access_token:
             logger.warning("StockTwits Access Token not configured. Skipping StockTwits sentiment.")
             return None
             
        params = {'limit': 30, 'access_token': access_token} # Add access token

        try:
            response = requests.get(api_url, params=params, timeout=10)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            
            data = response.json()
            messages = data.get('messages', [])

            if not messages:
                logger.info(f"No recent StockTwits messages found for {self.symbol} via API.")
                empty_result = {'score': None, 'polarity': None, 'analyzed_count': 0}
                self.cache.set_cache(cache_key, empty_result)
                return empty_result

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching StockTwits data for {self.symbol} via requests: {e}")
            return None
        except json.JSONDecodeError as e:
             logger.error(f"Error decoding StockTwits JSON response for {self.symbol}: {e}")
             return None
        except Exception as e:
            logger.error(f"Unexpected error fetching StockTwits data for {self.symbol}: {e}")
            return None

        total_polarity = 0
        analyzed_count = 0

        for message in messages:
            try:
                body = message.get('body')
                if not body or not isinstance(body, str):
                    continue
                
                # Basic cleaning - remove URLs which can skew sentiment
                cleaned_body = ' '.join(word for word in body.split() if not word.startswith('http'))
                
                # Use VADER for sentiment scoring
                vs = self.vader_analyzer.polarity_scores(cleaned_body)
                total_polarity += vs['compound'] # Use VADER's compound score
                analyzed_count += 1
            except Exception as e:
                logger.error(f"Error analyzing StockTwits message ID {message.get('id')}: '{body}'. Error: {e}")

        if analyzed_count == 0:
            logger.warning(f"Could not analyze any fetched StockTwits messages for {self.symbol}")
            empty_result = {'score': None, 'polarity': None, 'analyzed_count': 0}
            self.cache.set_cache(cache_key, empty_result)
            return empty_result

        average_polarity = total_polarity / analyzed_count

        # Convert polarity (-1 to 1) to a score (0 to 1)
        sentiment_score = (average_polarity + 1) / 2

        result = {
            'score': sentiment_score,
            'polarity': average_polarity,
            'analyzed_count': analyzed_count
        }

        # Save to cache before returning
        self.cache.set_cache(cache_key, result)

        return result

    def get_sentiment_trends(self, days=7):
        """
        Get sentiment trends over a specified period.

        Args:
            days (int): Number of days to look back for trend analysis.

        Returns:
            dict: Data representing the sentiment trend over the period.
                  Returns None if analysis fails.
        """
        logger.debug(f"Calculating sentiment trend for {self.symbol} over {days} days")
        
        history_dir = os.path.join(self.cache.cache_dir, 'sentiment_history')
        if not os.path.exists(history_dir):
            logger.warning("Sentiment history directory does not exist.")
            return {'trend': 'stable', 'scores_analyzed': 0} # Default to stable if no history

        all_scores = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Iterate through dates in the range
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y%m%d')
            file_path = os.path.join(history_dir, f"{self.symbol}_{date_str}.json")
            
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        daily_history = json.load(f)
                        if isinstance(daily_history, list):
                            # Extract scores, potentially filter by timestamp if needed later
                            for entry in daily_history:
                                if 'score' in entry and entry['score'] is not None:
                                     # Store score and timestamp for potential sorting/filtering
                                     entry_time = datetime.fromisoformat(entry['timestamp'])
                                     if start_date <= entry_time <= end_date:
                                         all_scores.append(entry['score'])
                except json.JSONDecodeError:
                    logger.warning(f"Could not decode JSON from history file {file_path}")
                except Exception as e:
                    logger.error(f"Error reading history file {file_path}: {e}")
            
            current_date += timedelta(days=1)

        if len(all_scores) < 2: # Need at least two points to determine a trend
            logger.info(f"Not enough historical sentiment data points ({len(all_scores)}) for {self.symbol} to determine trend.")
            return {'trend': 'stable', 'scores_analyzed': len(all_scores)}

        # Simple trend calculation: compare average of first half vs second half
        midpoint = len(all_scores) // 2
        first_half_avg = sum(all_scores[:midpoint]) / midpoint if midpoint > 0 else 0
        second_half_avg = sum(all_scores[midpoint:]) / (len(all_scores) - midpoint) if (len(all_scores) - midpoint) > 0 else 0

        trend = 'stable'
        # Define a threshold for significant change (e.g., 5% change relative to the first half)
        change_threshold = 0.05
        relative_change = (second_half_avg - first_half_avg) / first_half_avg if first_half_avg != 0 else 0

        if second_half_avg > first_half_avg and relative_change > change_threshold:
            trend = 'improving'
        elif second_half_avg < first_half_avg and abs(relative_change) > change_threshold:
            trend = 'declining'
            
        logger.debug(f"Sentiment trend for {self.symbol}: {trend} (First half avg: {first_half_avg:.3f}, Second half avg: {second_half_avg:.3f})")

        return {'trend': trend, 'scores_analyzed': len(all_scores)}

# Placeholder for API client classes (to be implemented or imported)
class TwitterAPI:
    """Placeholder for Twitter/X API client"""
    def __init__(self, api_key):
        self.api_key = api_key
        logger.info("TwitterAPI initialized (Placeholder)")

class RedditAPI:
    """Placeholder for Reddit API client"""
    def __init__(self, api_key):
        self.api_key = api_key
        logger.info("RedditAPI initialized (Placeholder)")

class StocktwitsAPI:
    """Placeholder for StockTwits API client"""
    def __init__(self, api_key):
        self.api_key = api_key
        logger.info("StocktwitsAPI initialized (Placeholder)")