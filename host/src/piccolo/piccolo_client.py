"""Host-side client for the Piccolo Red Pitaya FastAPI server.

Replaces the four raw-socket clients with:
  - httpx (synchronous) for commands and register snapshots (REST), and
  - websockets (synchronous) for the ADC and droplet streams, each running in a
    daemon thread with automatic reconnect.

The streaming callbacks keep the same signatures the controller expects:
  adc_callback(ch0, ch1, ch2, ch3)   # each a numpy array of ADC_BUFFER samples
  droplet_callback(fpga_vars_dict)
"""

import time
import json
import struct
import logging
import threading

import numpy as np
import httpx
from websockets.sync.client import connect as ws_connect

logger = logging.getLogger(__name__)

# Streaming layout — must match firmware/arm/piccolo_api.py and the FADS RTL.
API_PORT = 8000
N_CHANNELS = 4
ADC_BUFFER = 4096
_RECONNECT_BACKOFF_S = 1.0
_WS_RECV_TIMEOUT_S = 5.0


class PiccoloClient:
    """Single client for the Red Pitaya FastAPI server (REST + WebSocket streams)."""

    def __init__(self, host, port=API_PORT, adc_callback=None, droplet_callback=None,
                 timeout=5.0):
        self.host = host
        self.port = port
        self.adc_callback = adc_callback
        self.droplet_callback = droplet_callback

        self._base_url = f"http://{host}:{port}"
        self._ws_base = f"ws://{host}:{port}"
        self._http = httpx.Client(base_url=self._base_url, timeout=timeout)

        self._stop = threading.Event()
        self._threads = []

    # ---------------- REST: commands & snapshot ----------------

    def wait_until_ready(self, timeout=20.0, interval=0.5):
        """Poll /health until the server responds or the timeout elapses."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if self._http.get("/health").status_code == 200:
                    logger.info("Red Pitaya API ready at %s", self._base_url)
                    return True
            except Exception:
                pass
            time.sleep(interval)
        logger.warning("Red Pitaya API not ready after %ss at %s", timeout, self._base_url)
        return False

    def set_register(self, name, value):
        """Set one FPGA register."""
        try:
            self._http.post(f"/registers/{name}", json={"value": value})
        except Exception as e:
            logger.error("set_register(%s=%s) failed: %s", name, value, e)

    def get_registers(self):
        """Return a snapshot dict of all FPGA registers, or {} on failure."""
        try:
            return self._http.get("/registers").json()
        except Exception as e:
            logger.error("get_registers failed: %s", e)
            return {}

    def shutdown(self):
        """Ask the Red Pitaya server process to exit."""
        try:
            self._http.post("/shutdown")
            logger.info("Shutdown command sent to Red Pitaya.")
        except Exception:
            # The server exits mid-request, so a dropped connection is expected.
            logger.info("Shutdown command sent (connection closed by server).")

    # ---------------- WebSocket streams ----------------

    def start(self):
        """Start the ADC and droplet streaming threads."""
        self._stop.clear()
        self._threads = [
            threading.Thread(target=self._adc_loop, name="adc-stream", daemon=True),
            threading.Thread(target=self._droplet_loop, name="droplet-stream", daemon=True),
        ]
        for t in self._threads:
            t.start()
        logger.info("Streaming threads started.")

    def stop(self):
        """Stop the streaming threads (leaves the HTTP client open for shutdown())."""
        self._stop.set()
        for t in self._threads:
            t.join(timeout=2.0)
        self._threads = []
        logger.info("Streaming threads stopped.")

    def close(self):
        """Close the underlying HTTP client."""
        self._http.close()

    def _adc_loop(self):
        n = N_CHANNELS * ADC_BUFFER
        while not self._stop.is_set():
            try:
                with ws_connect(f"{self._ws_base}/ws/adc", max_size=None) as ws:
                    logger.info("ADC stream connected.")
                    while not self._stop.is_set():
                        try:
                            msg = ws.recv(timeout=_WS_RECV_TIMEOUT_S)
                        except TimeoutError:
                            continue
                        if not isinstance(msg, (bytes, bytearray)):
                            continue  # ignore stray text frames
                        floats = struct.unpack(f"<{n}f", msg)
                        arr = np.asarray(floats, dtype=float)
                        chans = [arr[i * ADC_BUFFER:(i + 1) * ADC_BUFFER] for i in range(N_CHANNELS)]
                        if self.adc_callback:
                            self.adc_callback(*chans)
            except Exception as e:
                if self._stop.is_set():
                    break
                logger.warning("ADC stream error (%s); reconnecting...", e)
                time.sleep(_RECONNECT_BACKOFF_S)

    def _droplet_loop(self):
        while not self._stop.is_set():
            try:
                with ws_connect(f"{self._ws_base}/ws/droplets", max_size=None) as ws:
                    logger.info("Droplet stream connected.")
                    while not self._stop.is_set():
                        try:
                            msg = ws.recv(timeout=_WS_RECV_TIMEOUT_S)
                        except TimeoutError:
                            continue
                        if isinstance(msg, (bytes, bytearray)):
                            msg = msg.decode()
                        fpga_vars = json.loads(msg)
                        if self.droplet_callback:
                            self.droplet_callback(fpga_vars)
            except Exception as e:
                if self._stop.is_set():
                    break
                logger.warning("Droplet stream error (%s); reconnecting...", e)
                time.sleep(_RECONNECT_BACKOFF_S)
