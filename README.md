# Piccolo

Piccolo is a fluorescence-activated droplet sorting (FADS) instrument control system. It provides real-time detection, analysis, and sorting of microfluidic droplets based on multi-channel fluorescence signals.

## Screenshot

![social_preview](/social_preview.png?raw=true)

## Quickstart

### Installation

```bash
cd host
pip install -e .
```

For camera support (requires [Basler pylon SDK](https://www.baslerweb.com/en/software/pylon/) installed separately):

```bash
pip install -e ".[camera]"
```

### Running

```bash
# Simulation mode (no hardware required)
python -m piccolo --simulate

# Real hardware (path is relative to where you run from)
python -m piccolo --no-simulate --rp-login ../config/rp_login.json

# All options
python -m piccolo --help
```

The web interface launches at `http://127.0.0.1:8050/`.

### CLI Options

| Flag | Description |
|---|---|
| `--simulate` | Run with synthetic data (no hardware required) |
| `--no-simulate` | Connect to real hardware |
| `--config PATH` | YAML config file (default: `config/default.yaml`) |
| `--rp-login PATH` | Red Pitaya login JSON (IP, username, password) |
| `--no-camera` | Disable camera even if enabled in config |
| `--no-launch-rp` | Skip deploying code to the Red Pitaya |
| `--port PORT` | Dash server port (default: 8050) |
| `--no-browser` | Don't auto-open browser on startup |
| `--verbose` | Enable verbose output |

### Running Tests

```bash
pip install -e ".[dev]"
pytest
```

## Architecture

The system spans three build targets (host PC, Red Pitaya ARM, and FPGA), connected over HTTP/WebSocket (a FastAPI server on the Red Pitaya). On the host side, the code is layered so that the UI never talks to hardware directly — it goes through a controller, which delegates to drivers and the API client.

```
                                                                    SiPM Detectors
 Host PC                              Red Pitaya                    (fluorescence)
┌─────────────────────────────┐      ┌──────────────────────────┐
│                             │      │                          │  ┌──────┐
│  ┌───────────────────────┐  │      │  ┌────────────────────┐◄─┼──│SiPM 0│
│  │  UI                   │  │      │  │  FPGA              │◄─┼──┤SiPM 1│
│  │  layout + callbacks   │  │      │  │  4-ch ADC          │◄─┼──┤SiPM 2│
│  └──────────┬────────────┘  │      │  │  - droplet detect  │◄─┼──┤SiPM 3│
│             │               │      │  │  - sort trigger ───┼──┼──┼─► Sorter
│  ┌──────────▼────────────┐  │      │  └────────▲───────────┘  │  └──────┘
│  │  Controller           │  │      │           │ mmap         │
│  │  HardwareController   │  │      │  ┌────────▼───────────┐  │
│  │    or                 │  │      │  │  ARM               │  │
│  │  HardwareSimulator    │  │      │  │  piccolo_api.py    │  │
│  └──┬─────────┬──────────┘  │      │  │  - mmap registers  │  │
│     │         │             │      │  │  - FastAPI server  │  │
│  ┌──▼───┐ ┌──▼───────────┐  │      │  └────────────────────┘  │
│  │Laser │ │PiccoloClient │──┼─HTTP/WS───────────┘             │
│  │Camera│ │(REST + WS)   │  │      │                          │
│  │      │ │              │  │      └──────────────────────────┘
│  └──────┘ └──────────────┘  │
│                             │
└─────────────────────────────┘
```

**Controllers** make decisions (detection, gating, data buffering). They implement a shared `InstrumentController` interface so the UI works identically with real hardware or simulation.

**Drivers** own a hardware resource (laser serial port, camera USB). **`PiccoloClient`** speaks REST (commands) and WebSocket (ADC + droplet streams) to the Red Pitaya's FastAPI server.

## Repository Structure

```
piccolo/
├── host/                              # Everything that runs on the PC
│   ├── pyproject.toml                 # Package metadata + dependencies
│   ├── src/piccolo/
│   │   ├── __main__.py                # Entry point: python -m piccolo
│   │   ├── config.py                  # Config loading from YAML
│   │   ├── conversion.py             # Unit conversion (raw ↔ volts, register display)
│   │   ├── piccolo_client.py          # PiccoloClient — REST + WebSocket client for the RP API
│   │   ├── controllers/
│   │   │   ├── controller.py          # InstrumentController ABC
│   │   │   ├── hardware_controller.py # Real hardware controller
│   │   │   └── hardware_simulator.py  # Simulation controller
│   │   ├── drivers/
│   │   │   ├── laser.py               # LaserBox — Cobalt Skyra serial driver
│   │   │   └── camera.py              # CameraManager — Basler pypylon driver
│   │   └── ui/
│   │       ├── app.py                 # Dash app factory
│   │       ├── layout.py              # UI layout definitions
│   │       ├── callbacks.py           # All Dash callbacks
│   │       └── assets/                # CSS stylesheets
│   └── tests/
│       ├── test_conversion.py
│       ├── test_hardware_simulator.py
│       ├── test_config.py
│       └── test_piccolo_client.py
├── firmware/                          # Everything deployed to the Red Pitaya
│   ├── arm/
│   │   ├── piccolo_api.py             # FastAPI server (REST + WebSocket) — entry point
│   │   ├── piccolo_rp.py              # PiccoloRP hardware layer (mmap + ADC acquisition)
│   │   └── requirements.txt           # RP-side deps (fastapi, uvicorn, websockets)
│   └── fpga/                          # RTL + bitstream
│       ├── rtl/                       # SystemVerilog source
│       ├── piccolo.bit.bin            # Compiled bitstream
│       └── BUILD.md                   # How to rebuild the bitstream (Vivado + phys_opt)
├── config/                            # Shared configuration
│   ├── default.yaml                   # Runtime config (all settings in one place)
│   ├── rp_login.json                  # Red Pitaya SSH credentials (gitignored)
│   ├── laser_config.json              # Laser box setup
│   └── piccolo_mmap.json             # FPGA register map (shared by host + firmware)
└── README.md
```

## Key Features

- **4-channel fluorescence detection** — simultaneous acquisition of droplet intensity, width, and area on all channels
- **Real-time FPGA gating** — per-channel low/high thresholds on intensity, width, and area for sort decisions
- **Interactive scatter plot gating** — box-select regions on density scatter plots to define sort gates
- **Multi-laser control** — on/off and power control for 405, 488, 561, and 633 nm lasers
- **Live camera feed** — MJPEG stream from a Basler camera with exposure and hardware trigger controls
- **FPGA register editor** — read and write all FPGA registers with automatic unit conversion
- **Data logging** — export droplet scatter data and raw ADC signals to CSV
- **Simulation mode** — full UI with synthetic data for development without hardware

## FPGA Register Units

The FPGA runs at **125 MHz** (8 ns per clock cycle). Register values are stored in raw FPGA units and converted for display:

| Register | Raw unit | Display unit | Conversion |
|---|---|---|---|
| Intensity thresholds | 14-bit signed ADC | V | Calibration: `(raw − offset) × gain / 8192 × 20` |
| Width thresholds | Clock cycles | ms | `÷ 125,000` |
| Area thresholds | Clock cycles × raw ADC | V·ms | `raw_to_volts() ÷ 125,000` |
| Sort delay / duration | µs | µs | Passthrough |
| Camera trigger delay / duration | µs | µs | Passthrough |
| Droplet frequency | Period in µs | Hz | `1,000,000 ÷ value` |

## Communication Protocol

The Red Pitaya runs a single **FastAPI** server (`firmware/arm/piccolo_api.py`, default
port `8000`); the host talks to it via `PiccoloClient`
(`host/src/piccolo/piccolo_client.py`) using REST for commands and WebSockets for
streaming.

| Endpoint | Type | Direction | Description |
|---|---|---|---|
| `GET /health` | REST | PC → RP | Liveness probe; the host waits on this before streaming |
| `GET /registers` | REST | PC → RP | Snapshot of all FPGA registers (JSON) |
| `POST /registers/{name}` | REST | PC → RP | Set one FPGA register — body `{"value": <int\|str>}` |
| `POST /shutdown` | REST | PC → RP | Stop the server process |
| `WS /ws/adc` | WebSocket | RP → PC | 4-channel ADC frames, little-endian float32 (4096 samples/ch), ~15 Hz |
| `WS /ws/droplets` | WebSocket | RP → PC | Droplet/register snapshots as JSON, sent on each new droplet |

**Interactive API docs** (auto-generated by FastAPI, served from the RP while it runs):

- Swagger UI: `http://<rp-ip>:8000/docs`
- ReDoc: `http://<rp-ip>:8000/redoc`
- OpenAPI schema: `http://<rp-ip>:8000/openapi.json`

Install the server deps on the Red Pitaya once with
`sudo pip3 install -r firmware/arm/requirements.txt` (pinned for the board's 32-bit ARM;
the `rp` API module ships with the Red Pitaya image).

## Hardware

| Component | Model | Role |
|---|---|---|
| FPGA board | Red Pitaya STEMlab (4-input variant) | ADC acquisition, real-time droplet detection and sort triggering |
| Excitation Lasers | Cobalt Skyra | Multi-line laser source (405, 488, 561, 633 nm) |
| Emission Detectors | SiPM photodetectors (x4) | Fluorescence signal detection, one per channel |
| Camera | Basler (USB3, Mono12p, 2048x2048) | Microscope imaging of the microfluidic chip |
| Sorter | Actuator (driven by FPGA digital output) | Deflects droplets matching gate criteria |
| Microfluidic chip | Custom | Generates and routes droplets through the detection/sort region |

## Dependencies

Core dependencies are managed via `host/pyproject.toml`:

- `dash`, `plotly`, `dash-bootstrap-components` — web UI
- `paramiko`, `scp` — SSH/SCP to Red Pitaya (deploy + launch)
- `httpx`, `websockets` — REST + WebSocket client for the Red Pitaya FastAPI server
- `numpy`, `pandas`, `scipy` — data handling and analysis
- `pyserial` — laser box serial communication
- `pyyaml` — configuration loading

The Red Pitaya server has its own dependencies (`firmware/arm/requirements.txt`:
`fastapi`, `uvicorn`, `websockets`, `pydantic<2`).

Optional (install with `pip install -e ".[camera]"`):

- `opencv-python` — camera frame processing
- `pypylon` — Basler camera Python bindings (requires [pylon Viewer/SDK](https://www.baslerweb.com/en/software/pylon/) installed on the system)
