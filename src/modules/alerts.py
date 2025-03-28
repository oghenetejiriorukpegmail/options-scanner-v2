"""
Alerts Module

Manages real-time alerts for trading setups based on scanner results
and user-defined conditions.
"""

import logging
import json
import os
from datetime import datetime
import smtplib # Added for email
from email.mime.text import MIMEText # Added for email formatting
from collections import deque # Added for browser alert queue
import threading # Added for queue lock

logger = logging.getLogger(__name__)

class AlertsManager:
    """
    Manages real-time alerts for trading setups.

    Features:
    - Custom alert conditions (Planned)
    - Multiple notification methods (Planned)
    - Alert history tracking (Planned)
    """

    def __init__(self, config=None):
        """
        Initialize the Alerts Manager.

        Args:
            config (dict, optional): Configuration dictionary, typically loaded from config.json.
        """
        self.config = config or self._load_config() # Load main config for settings like email
        self.alerts_config = self.config.get('alerts', {})
        self.alerts_file_path = 'user_alerts.json' # Define path for user alerts
        self.history_file_path = 'alert_history.json' # Define path for history
        self.max_history_size = 100 # Limit history entries
        self.user_alerts = self._load_user_alerts() # Load user alerts from dedicated file
        self.triggered_history = self._load_alert_history() # Load history from file
        self.notifiers = self._initialize_notifiers()
        # Queue for browser notifications (thread-safe)
        self.browser_alert_queue = deque(maxlen=50) # Limit queue size
        self.browser_alert_lock = threading.Lock()
        logger.info(f"AlertsManager initialized with {len(self.user_alerts)} user alerts from {self.alerts_file_path}.")

    def _load_config(self, config_file='config.json'):
        """Load alerts configuration"""
        # Basic default structure
        default_config = {
            "alerts": {
                "enabled": False,
                "check_interval_seconds": 300,
                "notification_methods": ["browser"],
                "email_settings": {
                    "smtp_server": None,
                    "smtp_port": 587,
                    "username": None,
                    "password": None,
                    "recipients": []
                }
                # Add webhook settings if needed
            }
        }
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    user_config = json.load(f)
                    if 'alerts' in user_config:
                        # Deep merge might be better here if structure gets complex
                        default_config['alerts'].update(user_config['alerts'])
            else:
                logger.warning(f"Config file {config_file} not found, using default alerts config.")
        except Exception as e:
            logger.error(f"Error loading alerts config from {config_file}: {e}")
        
        return default_config

    def _load_user_alerts(self):
        """Loads user-defined alerts from the JSON file."""
        if os.path.exists(self.alerts_file_path):
            try:
                with open(self.alerts_file_path, 'r') as f:
                    alerts = json.load(f)
                    if isinstance(alerts, list):
                        logger.info(f"Loaded {len(alerts)} user alerts from {self.alerts_file_path}")
                        return alerts
                    else:
                        logger.warning(f"Invalid format in {self.alerts_file_path}, expected a list. Starting fresh.")
                        return []
            except json.JSONDecodeError:
                logger.error(f"Error decoding JSON from {self.alerts_file_path}. Starting fresh.")
                return []
            except Exception as e:
                logger.error(f"Error loading user alerts from {self.alerts_file_path}: {e}")
                return []
        else:
            logger.info(f"User alerts file {self.alerts_file_path} not found. Starting with no alerts.")
            return []

    def _save_user_alerts(self):
        """Saves the current user alerts to the JSON file."""
        try:
            with open(self.alerts_file_path, 'w') as f:
                json.dump(self.user_alerts, f, indent=2)
            logger.info(f"Saved {len(self.user_alerts)} user alerts to {self.alerts_file_path}")
        except Exception as e:
            logger.error(f"Error saving user alerts to {self.alerts_file_path}: {e}")

    def _load_alert_history(self):
        """Loads triggered alert history from the JSON file."""
        if os.path.exists(self.history_file_path):
            try:
                with open(self.history_file_path, 'r') as f:
                    history = json.load(f)
                    if isinstance(history, list):
                        # Ensure history doesn't exceed max size on load
                        trimmed_history = history[-self.max_history_size:]
                        logger.info(f"Loaded {len(trimmed_history)} alert history entries from {self.history_file_path}")
                        return deque(trimmed_history, maxlen=self.max_history_size) # Use deque for efficient size limiting
                    else:
                        logger.warning(f"Invalid format in {self.history_file_path}, expected a list. Starting fresh.")
                        return deque(maxlen=self.max_history_size)
            except json.JSONDecodeError:
                logger.error(f"Error decoding JSON from {self.history_file_path}. Starting fresh.")
                return deque(maxlen=self.max_history_size)
            except Exception as e:
                logger.error(f"Error loading alert history from {self.history_file_path}: {e}")
                return deque(maxlen=self.max_history_size)
        else:
            logger.info(f"Alert history file {self.history_file_path} not found. Starting fresh.")
            return deque(maxlen=self.max_history_size)

    def _save_alert_history(self):
        """Saves the current alert history to the JSON file."""
        try:
            with open(self.history_file_path, 'w') as f:
                # Convert deque to list for JSON serialization
                json.dump(list(self.triggered_history), f, indent=2)
            logger.debug(f"Saved {len(self.triggered_history)} alert history entries to {self.history_file_path}")
        except Exception as e:
            logger.error(f"Error saving alert history to {self.history_file_path}: {e}")

    def _initialize_notifiers(self):
        """Initialize configured notification handlers."""
        notifiers = {}
        enabled_methods = self.alerts_config.get('notification_methods', [])
        
        if 'email' in enabled_methods:
            notifiers['email'] = EmailNotifier(self.alerts_config.get('email_settings', {}))
        if 'webhook' in enabled_methods:
            # Assuming webhook URL is stored directly under 'alerts' or a 'webhook_settings' dict
            webhook_url = self.alerts_config.get('webhook_url') 
            if webhook_url:
                 notifiers['webhook'] = WebhookNotifier(webhook_url)
            else:
                 logger.warning("Webhook notification enabled but no URL configured.")
        if 'browser' in enabled_methods:
            # BrowserNotifier might not need specific config here, handled via frontend/SSE
            notifiers['browser'] = BrowserNotifier()
            
        logger.info(f"Initialized notifiers: {list(notifiers.keys())}")
        return notifiers

    def check_alerts(self, scan_results):
        """
        Check scan results against user-defined alert conditions.

        Args:
            scan_results (list): A list of dictionaries, where each dictionary
                                 represents a potential trade setup found by the scanner.
        """
        if not self.alerts_config.get('enabled', False):
            logger.debug("Alerts are disabled in config.")
            return

        logger.info(f"Checking {len(scan_results)} scan results against {len(self.user_alerts)} alerts.")
        
        triggered_alerts = []
        
        # Iterate through configured user alerts and check against results
        for alert_rule in self.user_alerts:
            conditions = alert_rule.get('conditions', {})
            if not conditions: # Skip rules with no conditions
                 continue
                 
            for result in scan_results:
                if self._matches_conditions(result, conditions):
                    # Check if this specific alert/symbol combo was recently triggered (to avoid spam)
                    # TODO: Implement debounce/throttling logic if needed
                    
                    triggered_alerts.append({'alert': alert_rule, 'result': result})
                    logger.info(f"Alert '{alert_rule.get('name', 'Unnamed')}' triggered for symbol {result.get('symbol')}")
                    # Optional: break inner loop if only one alert per result is desired
                    # break
        
        if triggered_alerts:
            logger.info(f"Total triggered alerts in this cycle: {len(triggered_alerts)}")
            for triggered in triggered_alerts:
                self.send_notification(triggered['alert'], triggered['result'])
                self._add_to_history(triggered['alert'], triggered['result'])
        else:
            logger.debug("No alerts triggered in this scan cycle.")

    def _matches_conditions(self, result, conditions):
        """Checks if a scan result matches the alert conditions."""
        # TODO: Implement detailed condition matching logic
        # This will involve comparing fields in 'result' (e.g., result['symbol'], 
        # result['confidence'], result['setup'], result['market_context']['rsi'], etc.)
        # against the criteria defined in 'conditions'.
        # Example conditions format: {'min_confidence': 75, 'trend': ['bullish'], 'symbol': ['TSLA', 'AAPL']}
        
        try:
            for key, condition_value in conditions.items():
                # --- Basic Fields ---
                if key == 'symbol':
                    if not isinstance(condition_value, list) or result.get('symbol') not in condition_value:
                        return False
                elif key == 'setup':
                     # Allow matching prefixes (e.g., "bullish" matches "bullish_breakout")
                     result_setup = result.get('setup', '')
                     if not isinstance(condition_value, list) or not any(result_setup.startswith(cond) for cond in condition_value):
                          return False
                elif key == 'min_confidence':
                    if result.get('confidence') is None or result['confidence'] < condition_value:
                        return False
                elif key == 'max_confidence':
                     if result.get('confidence') is None or result['confidence'] > condition_value:
                          return False

                # --- Market Context Fields ---
                elif key in ['trend', 'sentiment', 'momentum']: # These are direct string comparisons
                     mk_context = result.get('market_context', {})
                     if not isinstance(condition_value, list) or mk_context.get(key) not in condition_value:
                          return False
                elif key == 'pcr_min':
                     mk_context = result.get('market_context', {})
                     if mk_context.get('pcr') is None or mk_context['pcr'] < condition_value:
                          return False
                elif key == 'pcr_max':
                     mk_context = result.get('market_context', {})
                     if mk_context.get('pcr') is None or mk_context['pcr'] > condition_value:
                          return False
                elif key == 'rsi_min':
                     mk_context = result.get('market_context', {})
                     if mk_context.get('rsi') is None or mk_context['rsi'] < condition_value:
                          return False
                elif key == 'rsi_max':
                     mk_context = result.get('market_context', {})
                     if mk_context.get('rsi') is None or mk_context['rsi'] > condition_value:
                          return False
                # Add stoch_rsi_min/max if needed
                
                # --- Options Metrics Fields (Add more as needed) ---
                elif key == 'gex_direction':
                     options_metrics = result.get('options_metrics', {})
                     gex_data = options_metrics.get('gex', {})
                     if gex_data.get('gex_direction') != condition_value: # Assuming single string value
                          return False
                elif key == 'min_option_volume':
                     options_metrics = result.get('options_metrics', {})
                     vwiv_data = options_metrics.get('vwiv', {})
                     if vwiv_data.get('total_volume') is None or vwiv_data['total_volume'] < condition_value:
                          return False
                # Add min_open_interest, gamma_min etc. if required for alerts

                # --- Add other potential condition checks here ---
                
                else:
                    logger.warning(f"Unsupported condition key '{key}' in alert rule.")
                    # Optionally return False if unknown keys should invalidate the match
            
            # If all conditions passed
            return True
            
        except Exception as e:
            logger.error(f"Error matching conditions for symbol {result.get('symbol', 'N/A')}: {e}")
            return False

    def create_alert(self, alert_name, conditions, notification_methods):
        """
        Create a new user-defined alert rule. (Planned: Persistence needed)

        Args:
            alert_name (str): A user-friendly name for the alert.
            conditions (dict): The criteria for triggering the alert.
            notification_methods (list): List of methods to use (e.g., ['email', 'browser']).
        """
        # Add basic validation
        if not alert_name or not conditions or not notification_methods:
             logger.error("Cannot create alert: Missing name, conditions, or methods.")
             return None # Indicate failure

        new_alert = {
            'id': f"alert_{int(datetime.now().timestamp() * 1000)}", # Simple unique ID using milliseconds
            'name': alert_name,
            'conditions': conditions,
            'methods': notification_methods,
            'created_at': datetime.now().isoformat(),
            'is_active': True # Add an active flag
        }
        self.user_alerts.append(new_alert)
        self._save_user_alerts() # Save changes
        logger.info(f"Created and saved new alert rule: {alert_name} (ID: {new_alert['id']})")
        return new_alert # Return the created alert

    def delete_alert(self, alert_id):
        """Deletes an alert rule by its ID."""
        initial_len = len(self.user_alerts)
        self.user_alerts = [alert for alert in self.user_alerts if alert.get('id') != alert_id]
        if len(self.user_alerts) < initial_len:
            self._save_user_alerts() # Save changes
            logger.info(f"Deleted alert rule with ID: {alert_id}")
            return True
        else:
            logger.warning(f"Could not find alert rule with ID: {alert_id} to delete.")
            return False

    # Add methods to update alerts if needed (e.g., toggle active status)
    # def update_alert(self, alert_id, updates): ...

    def send_notification(self, alert, result):
        """
        Send notifications for a triggered alert using configured methods.

        Args:
            alert (dict): The alert rule that was triggered.
            result (dict): The scan result that matched the alert conditions.
        """
        alert_name = alert.get('name', 'Unnamed Alert')
        symbol = result.get('symbol', 'N/A')
        message = f"Alert '{alert_name}' triggered for {symbol}: Setup={result.get('setup')}, Confidence={result.get('confidence'):.1f}%"
        logger.info(f"Processing notification: {message}") # Changed log message slightly

        methods_to_use = alert.get('methods', [])
        
        for method_name in methods_to_use:
             # Special handling for browser notifications - add to queue
             if method_name == 'browser':
                  with self.browser_alert_lock:
                       # Store relevant info for the browser
                       browser_data = {
                            'type': 'alert', # Add type field for SSE handling
                            'name': alert_name,
                            'symbol': symbol,
                            'setup': result.get('setup'),
                            'confidence': result.get('confidence'),
                            'message': message # Include the formatted message
                       }
                       self.browser_alert_queue.append(browser_data)
                  logger.info(f"Added browser notification for '{alert_name}' ({symbol}) to queue.")
             else:
                  # Handle other notifiers (Email, Webhook)
                  notifier = self.notifiers.get(method_name)
                  if notifier:
                       try:
                            notifier.notify(subject=f"Scanner Alert: {symbol}", message=message, data={'alert': alert, 'result': result})
                       except Exception as e:
                            logger.error(f"Failed to send notification via {method_name}: {e}")
                  else:
                       logger.warning(f"Notification method '{method_name}' requested by alert but not configured/initialized.")

    def get_pending_browser_alerts(self):
        """Retrieves and clears pending browser alerts from the queue."""
        alerts = []
        with self.browser_alert_lock:
            while True:
                try:
                    alerts.append(self.browser_alert_queue.popleft())
                except IndexError:
                    break # Queue is empty
        return alerts

    def _add_to_history(self, alert, result):
        """Adds a triggered alert event to the history deque and saves."""
        history_entry = {
            'timestamp': datetime.now().isoformat(),
            'alert_name': alert.get('name', 'Unnamed'),
            'symbol': result.get('symbol', 'N/A'),
            # Store only key details to keep history file smaller
            'details': {
                'setup': result.get('setup'),
                'confidence': result.get('confidence'),
                'price': result.get('current_price')
            }
        }
        # Deque automatically handles maxlen when appending
        self.triggered_history.append(history_entry)
        self._save_alert_history() # Save after adding

    def get_alert_history(self):
        """
        Get the history of triggered alerts.

        Returns:
            list: A list of dictionaries representing triggered alert events (newest first).
        """
        # Return a reversed list so newest alerts appear first
        return list(reversed(self.triggered_history))

# --- Placeholder Notifier Classes ---

class BaseNotifier:
    """Base class for notification handlers."""
    def notify(self, subject, message, data=None):
        raise NotImplementedError

class EmailNotifier(BaseNotifier):
    """Email notification sender using smtplib."""
    def __init__(self, settings):
        # Store settings, ensure port is an int
        self.server = settings.get('smtp_server')
        self.port = int(settings.get('smtp_port', 587)) # Default to 587, ensure int
        self.username = settings.get('username')
        self.password = settings.get('password') # Consider more secure ways to handle passwords
        self.recipients = settings.get('recipients', [])
        logger.info("EmailNotifier initialized.")

    def notify(self, subject, message, data=None):
        logger.info(f"Attempting to send Email: Subject='{subject}'")
        
        if not self.server or not self.recipients:
             logger.warning("Email settings (server, recipients) not configured. Cannot send email.")
             return
             
        sender = self.username or f"scanner-alert@{self.server.split('.')[-2]}.com" # Construct a plausible sender

        # Create the email message
        msg = MIMEText(message)
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = ', '.join(self.recipients) # Join recipients for the header

        try:
            # Connect to SMTP server
            # Using SMTP_SSL for implicit TLS (common for ports 465), or starttls for port 587
            if self.port == 465:
                 server = smtplib.SMTP_SSL(self.server, self.port, timeout=10)
            else: # Assume port 587 or other requires STARTTLS
                 server = smtplib.SMTP(self.server, self.port, timeout=10)
                 server.starttls() # Secure the connection

            # Login if username/password are provided
            if self.username and self.password:
                server.login(self.username, self.password)
            
            # Send the email
            server.sendmail(sender, self.recipients, msg.as_string())
            logger.info(f"Email sent successfully to {', '.join(self.recipients)}")
            
            # Close the connection
            server.quit()

        except smtplib.SMTPAuthenticationError:
             logger.error(f"SMTP Authentication Error for email. Check username/password.")
        except smtplib.SMTPConnectError:
             logger.error(f"SMTP Connection Error. Could not connect to {self.server}:{self.port}.")
        except smtplib.SMTPServerDisconnected:
             logger.error(f"SMTP Server Disconnected unexpectedly.")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")

class WebhookNotifier(BaseNotifier):
    """Webhook notification sender."""
    def __init__(self, url):
        self.url = url
        logger.info(f"WebhookNotifier initialized for URL: {url}")

    def notify(self, subject, message, data=None):
        logger.info(f"Attempting to send Webhook: URL='{self.url}'")
        
        if not self.url:
             logger.warning("Webhook URL not configured. Cannot send webhook.")
             return
             
        # Use local import for requests to avoid top-level dependency if not used elsewhere often
        import requests
        
        # Structure the payload - adapt as needed for the receiving service (e.g., Slack, Discord)
        # This example uses a Slack-like structure
        payload = {
            'text': f"*{subject}*\n{message}",
            'attachments': [
                 {
                      "fallback": f"Details for {data.get('result', {}).get('symbol', 'N/A')}",
                      "fields": [
                           {"title": "Symbol", "value": data.get('result', {}).get('symbol', 'N/A'), "short": True},
                           {"title": "Setup", "value": data.get('result', {}).get('setup', 'N/A'), "short": True},
                           {"title": "Confidence", "value": f"{data.get('result', {}).get('confidence', 0):.1f}%", "short": True},
                           {"title": "Price", "value": f"${data.get('result', {}).get('current_price', 0):.2f}", "short": True},
                      ]
                 }
            ]
            # Add more details from 'data' (which contains 'alert' and 'result') if needed
        }
        
        try:
            response = requests.post(self.url, json=payload, timeout=10) # Increased timeout slightly
            response.raise_for_status() # Check for HTTP errors
            logger.info(f"Webhook sent successfully to {self.url}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending webhook to {self.url}: {e}")
        except Exception as e:
             logger.error(f"Unexpected error sending webhook: {e}")

class BrowserNotifier(BaseNotifier):
    """Browser notification sender (likely handled via SSE/WebSockets on frontend)."""
    def __init__(self):
        logger.info("BrowserNotifier initialized (Placeholder - relies on frontend implementation).")

    def notify(self, subject, message, data=None):
        # This might just log, assuming the actual push happens elsewhere
        # (e.g., via the SSE stream in app.py sending a specific event type)
        logger.info(f"Browser Notification Triggered: Subject='{subject}', Message='{message}'")
        # No actual sending logic here, frontend listens for alert events