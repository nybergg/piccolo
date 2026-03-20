"""
Piccolo UI app factory — creates and configures the Dash application.

Handles app initialization, MJPEG streaming route, and startup/shutdown.
"""

import os
import sys
import time
import signal
import logging
import webbrowser
from threading import Timer

import dash
import plotly.io as pio
import dash_bootstrap_components as dbc

from piccolo.controllers import HardwareSimulator, HardwareController
from piccolo.ui.layout import build_layout
from piccolo.ui.callbacks import register_callbacks


# ---- Configuration ----
SIMULATE = True
LAUNCH_RP = True
CAMERA_AVAILABLE = False  # Set True only if camera libs + hardware present
SERVER_URL = "http://127.0.0.1:8050/"


def create_app(controller, camera_manager=None):
    """Create and configure the Dash app."""
    pio.templates.default = "plotly_dark"
    external_stylesheets = [dbc.themes.CYBORG, dbc.icons.BOOTSTRAP, '/assets/custom.css']

    camera_available = camera_manager is not None

    app = dash.Dash(__name__,
                    title="Piccolo UI",
                    assets_folder=_find_assets_folder(),
                    external_stylesheets=external_stylesheets,
                    update_title=None)

    app.layout = build_layout(camera_available=camera_available, simulate=SIMULATE)
    register_callbacks(app, controller, camera_manager=camera_manager)

    if camera_available:
        _register_video_route(app, camera_manager)

    return app


def _find_assets_folder():
    """Locate the assets folder relative to the ui package."""
    assets_path = os.path.join(os.path.dirname(__file__), 'assets')
    if os.path.isdir(assets_path):
        return assets_path
    return None


def _register_video_route(app, camera_manager):
    """Register the /video_feed MJPEG streaming endpoint."""
    from flask import Response

    def generate_frames():
        while True:
            time.sleep(1/30)
            frame = camera_manager.get_latest_frame()
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    @app.server.route('/video_feed')
    def video_feed():
        return Response(generate_frames(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')


def main():
    """Main entry point — creates controller, app, and runs the server."""
    # Create controller
    if SIMULATE:
        controller = HardwareSimulator()
        controller.start()
    else:
        controller = HardwareController(rp_dir="piccolo_testing", verbose=True)
        if LAUNCH_RP:
            print("Launching Piccolo RP... please wait.")
            controller.launch_piccolo_rp()
            time.sleep(10)
        controller.start()
        time.sleep(1)

    # Create camera manager (if enabled)
    camera_manager = None
    if CAMERA_AVAILABLE:
        try:
            from piccolo.drivers.camera import CameraManager
            camera_manager = CameraManager()
            camera_manager.start()
            print("Camera started.")
        except ImportError:
            print("Camera libraries not available. Camera disabled.")
        except Exception as e:
            print(f"Camera init failed: {e}. Camera disabled.")

    # Create app
    app = create_app(controller, camera_manager=camera_manager)

    # Shutdown handler
    def cleanup():
        print("\nInitiating shutdown sequence...")
        if camera_manager:
            print("Stopping camera...")
            camera_manager.stop()
        print("Shutting down instrument...")
        try:
            controller.stop()
            print("Instrument stop called.")
        except Exception as e:
            print(f"Error during instrument stop: {e}")
        print("Cleanup finished.")

    def handle_signal(sig, frame):
        print(f"Received signal {sig}, initiating shutdown...")
        cleanup()
        time.sleep(0.5)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    try:
        signal.signal(signal.SIGTERM, handle_signal)
    except AttributeError:
        print("SIGTERM not available.")

    # Suppress werkzeug logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    # Check laser status
    if hasattr(controller, 'laser_box') and controller.laser_box:
        print("Laser control is available.")
    else:
        print("Laser control is DISABLED.")

    # Open browser and run
    print(f"Starting Dash server on {SERVER_URL} ... Press Ctrl+C to stop.")
    Timer(1.5, lambda: webbrowser.open_new_tab(SERVER_URL)).start()
    app.run(debug=False, port=8050)
    cleanup()


if __name__ == '__main__':
    main()
