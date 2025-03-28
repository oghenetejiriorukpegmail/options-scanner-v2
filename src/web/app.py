import sys
import os
import threading
import time
import json
from pathlib import Path
from flask import Flask, render_template, jsonify, Response, request

# Add the project root directory to Python path
project_root = str(Path(__file__).resolve().parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.modules.scanner import StockScanner
from src.modules.alerts import AlertsManager # Added import

class ProgressManager:
    def __init__(self):
        self.status = {
            'progress': 0,
            'message': 'Initializing...',
            'is_scanning': False,
            'current_symbol': None,
            'errors': [],
            'results': None
        }
        self.lock = threading.Lock()

    def update(self, progress, message, current_symbol=None):
        with self.lock:
            self.status['progress'] = min(100, max(0, progress))
            self.status['message'] = message
            if current_symbol:
                self.status['current_symbol'] = current_symbol

    def add_error(self, error):
        with self.lock:
            self.status['errors'].append(error)

    def set_results(self, results):
        with self.lock:
            self.status['results'] = results

    def get_status(self):
        with self.lock:
            return dict(self.status)

    def reset(self):
        with self.lock:
            self.status.update({
                'progress': 0,
                'message': 'Initializing...',
                'is_scanning': False,
                'current_symbol': None,
                'errors': [],
                'results': None
            })

def create_app():
    """Creates and configures the Flask application."""
    app = Flask(__name__,
        template_folder=str(Path(__file__).resolve().parent.parent.parent / 'templates'),
        static_folder=str(Path(__file__).resolve().parent.parent.parent / 'static'))

    progress_manager = ProgressManager()
    scanner_lock = threading.Lock()
    # Instantiate AlertsManager - it loads alerts from user_alerts.json
    alerts_manager = AlertsManager()

    def progress_callback(data):
        """Callback function for scanner progress updates"""
        progress_manager.update(
            data.get('progress', 0),
            data.get('message', 'Processing...'),
            data.get('current_symbol')
        )
        if 'error' in data:
            progress_manager.add_error(data['error'])

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/api/scan')
    def start_scan():
        filters = request.args.get('filters')
        if filters:
            try:
                filters = json.loads(filters)
            except json.JSONDecodeError:
                return jsonify({'error': 'Invalid filters format'}), 400
        else:
            filters = {}

        def generate_events():
            try:
                with scanner_lock:
                    if progress_manager.status['is_scanning']:
                        yield f"data: {json.dumps({'error': 'Scan already in progress'})}\n\n"
                        return

                    progress_manager.reset()
                    progress_manager.status['is_scanning'] = True

                    # Initialize scanner with progress callback
                    scanner = StockScanner(config_file='config.json', progress_callback=progress_callback)

                    # Update scanner config with user filters
                    scanner.config['filters'].update(filters)

                    # Start a background thread to run the scan
                    def run_scan_thread():
                        try:
                            # Run the scan
                            results = scanner.scan()

                            # Set the results in the progress manager
                            progress_manager.set_results(results)

                            # Final progress update
                            progress_manager.update(100, f"Scan complete. Found {len(results)} setups.")
                        except Exception as e:
                            progress_manager.add_error(f"Scan failed: {str(e)}")
                        finally:
                            progress_manager.status['is_scanning'] = False

                    # Start the scan in a background thread
                    scan_thread = threading.Thread(target=run_scan_thread)
                    scan_thread.daemon = True
                    scan_thread.start()

                    # Send progress updates while scanning
                    last_progress = -1
                    last_message = ""

                    # Send initial progress
                    yield f"data: {json.dumps({'progress': 0, 'message': 'Starting scan...'})}\n\n"

                    # Keep sending updates until scan is complete
                    while progress_manager.status['is_scanning']:
                        status = progress_manager.get_status()
                        current_progress = status['progress']
                        current_message = status.get('message', '')

                        # Only send update if progress or message has changed
                        if current_progress != last_progress or current_message != last_message:
                            yield f"data: {json.dumps({'progress': current_progress, 'message': current_message})}\n\n"
                            last_progress = current_progress
                            last_message = current_message

                            # Log progress to console
                            # print(f"Scan progress: {current_progress}% - {current_message}") # Reduce console noise

                        # Check for and send any pending browser alerts
                        pending_alerts = alerts_manager.get_pending_browser_alerts()
                        for alert_data in pending_alerts:
                             try:
                                  yield f"data: {json.dumps(alert_data)}\n\n" # Send alert data
                                  print(f"Sent browser alert: {alert_data.get('name')} for {alert_data.get('symbol')}")
                             except Exception as e:
                                  print(f"Error sending browser alert data: {e}")

                        time.sleep(0.5) # Check queue every 0.5 seconds

                    # Send final results
                    status = progress_manager.get_status()
                    if status['results']:
                        yield f"data: {json.dumps({'success': True, 'results': status['results']})}\n\n"
                    else:
                        yield f"data: {json.dumps({'error': 'Scan completed but no results were found'})}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                progress_manager.status['is_scanning'] = False

        return Response(generate_events(), mimetype="text/event-stream")

    @app.route('/api/results')
    def get_results():
        status = progress_manager.get_status()
        if status['results']:
            return jsonify({'success': True, 'results': status['results']})
        return jsonify({'success': False, 'message': 'No results available'})

    @app.route('/api/analyze/<symbol>')
    def analyze_symbol(symbol):
        try:
            scanner = StockScanner(config_file='config.json')
            result = scanner._analyze_symbol(symbol)
            if result:
                # Result already contains 'historical_chart_data' added in _analyze_symbol
                return jsonify({'success': True, 'result': result})
            return jsonify({'success': False, 'error': f'No analysis results for {symbol}'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/options_metrics/<symbol>')
    def get_options_metrics(symbol):
        try:
            from src.modules.options_metrics import OptionsMetricsAnalyzer
            analyzer = OptionsMetricsAnalyzer(symbol)
            metrics = analyzer.calculate_metrics()
            if metrics:
                # Prepare data for charts
                strikes = []
                gamma = []
                charm = []
                vanna = []
                vomma = []
                
                # Extract data from gamma profile
                if 'gamma_profile' in metrics:
                    for point in metrics['gamma_profile']:
                        strikes.append(point['strike'])
                        gamma.append(point['total_gamma'])
                
                # Extract data from second-order Greeks
                if 'charm' in metrics and metrics['charm']:
                    charm = [point.get('total_charm', 0) for point in metrics['charm']]
                
                if 'vanna' in metrics and metrics['vanna']:
                    vanna = [point.get('total_vanna', 0) for point in metrics['vanna']]
                
                if 'vomma' in metrics and metrics['vomma']:
                    vomma = [point.get('total_vomma', 0) for point in metrics['vomma']]
                
                # Format data for frontend
                chart_data = {
                    'strikes': strikes,
                    'gamma': gamma,
                    'charm': charm,
                    'vanna': vanna,
                    'vomma': vomma,
                    'high_gamma_strikes': metrics.get('high_gamma_strikes', []),
                    'gex': metrics.get('gex', {}).get('total_gex', 0),
                    'gex_by_strike': metrics.get('gex', {}).get('gex_by_strike', []), # Added GEX profile
                    'vwiv': metrics.get('vwiv', {}).get('vwiv', 0)
                }
                
                return jsonify({
                    'success': True,
                    'metrics': chart_data
                })
            return jsonify({'success': False, 'error': f'Could not calculate metrics for {symbol}'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    # --- Alert Management API Endpoints ---

    @app.route('/api/alerts', methods=['GET'])
    def get_alerts():
        """Returns the list of user-defined alerts."""
        # Return a copy to avoid modifying the original list directly
        return jsonify({'success': True, 'alerts': list(alerts_manager.user_alerts)})

    @app.route('/api/alerts', methods=['POST'])
    def add_alert():
        """Creates a new alert rule."""
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400
            
        name = data.get('name')
        conditions = data.get('conditions')
        methods = data.get('methods')

        if not name or not conditions or not methods:
            return jsonify({'success': False, 'error': 'Missing required fields: name, conditions, methods'}), 400

        try:
            new_alert = alerts_manager.create_alert(name, conditions, methods)
            if new_alert:
                 # Return the created alert, including its generated ID
                 return jsonify({'success': True, 'alert': new_alert}), 201
            else:
                 # create_alert might return None if validation fails
                 return jsonify({'success': False, 'error': 'Failed to create alert due to invalid data'}), 400
        except Exception as e:
            return jsonify({'success': False, 'error': f'Error creating alert: {str(e)}'}), 500

    @app.route('/api/alerts/<alert_id>', methods=['DELETE'])
    def delete_alert_route(alert_id):
        """Deletes an alert rule by its ID."""
        try:
            deleted = alerts_manager.delete_alert(alert_id)
            if deleted:
                return jsonify({'success': True, 'message': f'Alert {alert_id} deleted'})
            else:
                return jsonify({'success': False, 'error': f'Alert {alert_id} not found'}), 404
        except Exception as e:
            return jsonify({'success': False, 'error': f'Error deleting alert: {str(e)}'}), 500

    # TODO: Add PUT endpoint for updating alerts (e.g., toggling is_active) if needed
    # @app.route('/api/alerts/<alert_id>', methods=['PUT'])
    # def update_alert_route(alert_id): ...

    @app.route('/api/alerts/history', methods=['GET'])
    def get_alert_history_route():
        """Returns the history of triggered alerts."""
        try:
            history = alerts_manager.get_alert_history()
            return jsonify({'success': True, 'history': history})
        except Exception as e:
            return jsonify({'success': False, 'error': f'Error getting alert history: {str(e)}'}), 500

    return app