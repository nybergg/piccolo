"""
Piccolo entry point — python -m piccolo

Parses CLI arguments, loads config, creates the controller and UI,
and runs the Dash server.
"""

import argparse
import logging
import os
import signal
import sys
import time
import webbrowser
from threading import Timer

from piccolo.config import PiccoloConfig
from piccolo.controllers import HardwareSimulator, HardwareController
from piccolo.ui.app import create_app


def parse_args():
    parser = argparse.ArgumentParser(
        prog="piccolo",
        description="Piccolo FADS instrument control system",
    )
    parser.add_argument(
        "--config", default="config/default.yaml",
        help="Path to YAML config file (default: config/default.yaml)",
    )
    parser.add_argument(
        "--rp-login", default=None,
        help="Path to Red Pitaya login JSON (overrides config values)",
    )
    parser.add_argument(
        "--simulate", action="store_true", default=None,
        help="Run in simulation mode (no hardware required)",
    )
    parser.add_argument(
        "--no-simulate", action="store_true", default=None,
        help="Run with real hardware",
    )
    parser.add_argument(
        "--no-camera", action="store_true",
        help="Disable camera even if enabled in config",
    )
    parser.add_argument(
        "--no-launch-rp", action="store_true",
        help="Skip deploying/launching code on the Red Pitaya",
    )
    parser.add_argument(
        "--port", type=int, default=None,
        help="Dash server port (default: from config or 8050)",
    )
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Don't auto-open browser on startup",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable verbose output",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Load config
    config = PiccoloConfig.load(args.config, rp_login_path=args.rp_login)

    # CLI overrides
    if args.simulate:
        config.simulate = True
    elif args.no_simulate:
        config.simulate = False
    if args.no_camera:
        config.camera_enabled = False
    if args.no_launch_rp:
        config.launch_rp = False
    if args.port:
        config.server_port = args.port

    verbose = args.verbose

    # Create controller
    if config.simulate:
        print("Starting in SIMULATION mode.")
        controller = HardwareSimulator(verbose=verbose)
        controller.start()
    else:
        print("Starting with REAL HARDWARE.")
        controller = HardwareController(
            rp_dir=config.rp_dir,
            verbose=verbose,
        )
        if config.launch_rp:
            print("Launching Piccolo RP... please wait.")
            controller.launch_piccolo_rp()
            time.sleep(10)
        controller.start()
        time.sleep(1)

    # Create camera manager (if enabled)
    camera_manager = None
    if config.camera_enabled:
        try:
            from piccolo.drivers.camera import CameraManager
            camera_manager = CameraManager(verbose=verbose)
            camera_manager.start()
            print("Camera started.")
        except ImportError:
            print("Camera libraries not available. Camera disabled.")
        except Exception as e:
            print(f"Camera init failed: {e}. Camera disabled.")

    # Create app
    app = create_app(controller, camera_manager=camera_manager, simulate=config.simulate)

    # Shutdown handler
    _cleaned_up = False

    def cleanup():
        nonlocal _cleaned_up
        if _cleaned_up:
            return
        _cleaned_up = True
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
        print(f"\nReceived signal {sig}, shutting down...")
        cleanup()
        # Force-kill the process to ensure Werkzeug doesn't linger
        os._exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    try:
        signal.signal(signal.SIGTERM, handle_signal)
    except AttributeError:
        pass

    # Suppress werkzeug logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)

    # Check laser status
    if hasattr(controller, 'laser_box') and controller.laser_box:
        print("Laser control is available.")
    else:
        print("Laser control is DISABLED.")

    # Open browser and run
    server_url = f"http://127.0.0.1:{config.server_port}/"
    print(f"Starting Dash server on {server_url} ... Press Ctrl+C to stop.")
    if not args.no_browser:
        Timer(1.5, lambda: webbrowser.open_new_tab(server_url)).start()

    try:
        app.run(debug=False, port=config.server_port)
    finally:
        cleanup()


if __name__ == '__main__':
    main()
