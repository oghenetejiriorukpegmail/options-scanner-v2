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
                            print(f"Scan progress: {current_progress}% - {current_message}")

                        time.sleep(0.5)

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
                return jsonify({'success': True, 'result': result})
            return jsonify({'success': False, 'error': f'No analysis results for {symbol}'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    return app