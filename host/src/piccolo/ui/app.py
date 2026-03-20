"""
Piccolo UI app factory — creates and configures the Dash application.

Handles app initialization, MJPEG streaming route, and layout/callback wiring.
"""

import os
import time

import dash
import plotly.io as pio
import dash_bootstrap_components as dbc

from piccolo.ui.layout import build_layout
from piccolo.ui.callbacks import register_callbacks


def create_app(controller, camera_manager=None, simulate=False):
    """Create and configure the Dash app."""
    pio.templates.default = "plotly_dark"
    external_stylesheets = [dbc.themes.CYBORG, dbc.icons.BOOTSTRAP, '/assets/custom.css']

    camera_available = camera_manager is not None

    app = dash.Dash(__name__,
                    title="Piccolo UI",
                    assets_folder=_find_assets_folder(),
                    external_stylesheets=external_stylesheets,
                    update_title=None)

    app.layout = build_layout(camera_available=camera_available, simulate=simulate)
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
