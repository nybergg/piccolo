"""
Piccolo entry point — python -m piccolo

Parses CLI arguments, loads config, creates the controller and UI,
and runs the Dash server.
"""

import argparse
import logging
import os
import signal
import time
import webbrowser
from threading import Timer

from piccolo.config import PiccoloConfig
from piccolo.controllers import HardwareSimulator, HardwareController
from piccolo.ui.app import create_app

logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        prog="piccolo",
        description="Piccolo FADS instrument control system",
    )
    parser.add_argument(
        "--config", default="../config/default.yaml",
        help="Path to YAML config file (default: ../config/default.yaml)",
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

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s | %(name)s | %(message)s",
    )
    # Suppress noisy third-party loggers
    logging.getLogger('werkzeug').setLevel(logging.ERROR)

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
        logger.info("Starting in SIMULATION mode.")
        controller = HardwareSimulator(verbose=verbose)
        controller.start()
    else:
        logger.info("Starting with REAL HARDWARE.")
        controller = HardwareController(
            config=config,
            rp_dir=config.rp_dir,
            verbose=verbose,
        )
        if config.launch_rp:
            logger.info("Launching Piccolo RP... please wait.")
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
            logger.info("Camera started.")
        except ImportError as e:
            logger.warning("Camera libraries not available: %s. Camera disabled.", e)
        except Exception as e:
            logger.error("Camera init failed: %s. Camera disabled.", e)

    # Create app
    app = create_app(controller, camera_manager=camera_manager, simulate=config.simulate)

    # Shutdown handler
    _cleaned_up = False

    def cleanup():
        nonlocal _cleaned_up
        if _cleaned_up:
            return
        _cleaned_up = True
        logger.info("Initiating shutdown sequence...")
        if camera_manager:
            logger.info("Stopping camera...")
            camera_manager.stop()
        logger.info("Shutting down instrument...")
        try:
            controller.stop()
            logger.info("Instrument stop called.")
        except Exception as e:
            logger.error("Error during instrument stop: %s", e)
        logger.info("Cleanup finished.")

    def handle_signal(sig, frame):
        logger.info("Received signal %s, shutting down...", sig)
        cleanup()
        # Force-kill the process to ensure Werkzeug doesn't linger
        os._exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    try:
        signal.signal(signal.SIGTERM, handle_signal)
    except AttributeError:
        pass

    # Check laser status
    if hasattr(controller, 'laser_box') and controller.laser_box:
        logger.info("Laser control is available.")
    else:
        logger.info("Laser control is DISABLED.")

    # Open browser and run
    server_url = f"http://127.0.0.1:{config.server_port}/"
    logger.info("Starting Dash server on %s ... Press Ctrl+C to stop.", server_url)
    if not args.no_browser:
        Timer(1.5, lambda: webbrowser.open_new_tab(server_url)).start()

    try:
        app.run(debug=False, port=config.server_port)
    finally:
        cleanup()


if __name__ == '__main__':
    main()
