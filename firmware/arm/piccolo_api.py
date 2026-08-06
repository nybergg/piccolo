"""FastAPI network layer for the Piccolo Red Pitaya.

Replaces the four hand-rolled TCP servers with a single FastAPI app:

    GET  /health              -> liveness probe (host waits on this before streaming)
    GET  /registers           -> snapshot of all FPGA registers (JSON)
    POST /registers/{name}    -> set one FPGA register (body: {"value": <int|str>})
    POST /shutdown            -> stop the server process (replaces the opcode-99 kill)
    WS   /ws/adc              -> 4-channel ADC frames, little-endian float32, rate-limited
    WS   /ws/droplets         -> FPGA register/droplet snapshots as JSON, on new droplet_id

Run on the Red Pitaya with:  sudo python3 piccolo_api.py [--verbose] [--very_verbose]
Requires fastapi + uvicorn (see firmware/arm/requirements.txt).
"""

import os
import json
import asyncio
import argparse
import threading
from contextlib import asynccontextmanager
from typing import Union

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from piccolo_rp import PiccoloRP

# Network / streaming configuration
API_HOST = "0.0.0.0"
API_PORT = 8000
ADC_STREAM_HZ = 15        # ADC waveform frames per second (was: unthrottled)
DROPLET_POLL_S = 0.002    # how often to poll for a new droplet_id (send only on change)


class RegisterValue(BaseModel):
    # Ints for numeric registers, binary strings (e.g. "1111") for boolean registers.
    value: Union[int, str]


def build_app(piccolo: PiccoloRP) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        piccolo.start_acquisition()   # begin continuous ADC acquisition
        yield

    app = FastAPI(title="Piccolo RP API", version="2.0", lifespan=lifespan)

    # ---------------- REST: commands & snapshot ----------------

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/registers")
    def get_registers():
        return piccolo.get_all()

    @app.post("/registers/{name}")
    def set_register(name: str, body: RegisterValue):
        piccolo.set_var(var_name=name, value=body.value)
        return {"name": name, "value": body.value}

    @app.post("/shutdown")
    def shutdown():
        def _stop():
            piccolo.cleanup()
            os._exit(0)
        threading.Timer(0.2, _stop).start()
        return {"status": "shutting down"}

    # ---------------- WebSockets: streams ----------------

    @app.websocket("/ws/adc")
    async def ws_adc(ws: WebSocket):
        await ws.accept()
        period = 1.0 / ADC_STREAM_HZ
        try:
            while True:
                payload = piccolo.get_adc_payload()
                if payload is not None:
                    await ws.send_bytes(payload)
                await asyncio.sleep(period)
        except WebSocketDisconnect:
            pass
        except Exception as e:  # pragma: no cover - defensive
            print(f"[ws/adc] error: {e}")

    @app.websocket("/ws/droplets")
    async def ws_droplets(ws: WebSocket):
        await ws.accept()
        last_id = None
        try:
            while True:
                # mmap reads are quick but blocking; keep the event loop responsive.
                fpga_vars = await asyncio.to_thread(piccolo.get_all)
                cur_id = fpga_vars.get("droplet_id")
                if cur_id != last_id:      # send only when a new droplet is evaluated
                    last_id = cur_id
                    await ws.send_text(json.dumps(fpga_vars))
                await asyncio.sleep(DROPLET_POLL_S)
        except WebSocketDisconnect:
            pass
        except Exception as e:  # pragma: no cover - defensive
            print(f"[ws/droplets] error: {e}")

    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true", help="Enable verbose mode")
    parser.add_argument("--very_verbose", action="store_true", help="Enable very verbose mode")
    parser.add_argument("--port", type=int, default=API_PORT, help="TCP port to serve on")
    args = parser.parse_args()

    piccolo = PiccoloRP(verbose=args.verbose, very_verbose=args.very_verbose)
    app = build_app(piccolo)
    uvicorn.run(app, host=API_HOST, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
