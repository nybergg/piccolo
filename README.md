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

# Real hardware
python -m piccolo --no-simulate --rp-login config/rp_login.json

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

The system spans three build targets (host PC, Red Pitaya ARM, and FPGA) connected via TCP. On the host side, the code is layered so that the UI never talks to hardware directly — it goes through a controller, which delegates to drivers and clients.

```
 Host PC                              Red Pitaya
┌─────────────────────────────┐      ┌──────────────────────────┐
│                             │      │                          │
│  ┌───────────────────────┐  │      │  firmware/arm/           │
│  │  UI                   │  │      │  piccolo_rp.py           │
│  │  layout + callbacks   │  │      │  - mmap FPGA registers   │
│  └──────────┬────────────┘  │      │  - TCP servers (:5001-3) │
│             │               │      │                          │
│  ┌──────────▼────────────┐  │      └────────────▲─────────────┘
│  │  Controller           │  │                   │ TCP
│  │  HardwareController   │  │  ┌────────────────┘
│  │    or                 │  │  │
│  │  HardwareSimulator    │  │  │   ┌──────────────────────────┐
│  └──┬─────────┬──────────┘  │  │   │  FPGA                    │
│     │         │             │  │   │  - 4-ch ADC acquisition   │
│  ┌──▼───┐ ┌──▼──────────┐  │  │   │  - droplet detection     │
│  │Laser │ │TCP Clients   │──┼──┘   │  - sort trigger output   │
│  │Camera│ │(ADC, Memory, │  │      └──────────────────────────┘
│  │      │ │ Command)     │  │
│  └──────┘ └──────────────┘  │
│                             │
└─────────────────────────────┘
```

**Controllers** make decisions (detection, gating, data buffering). They implement a shared `InstrumentController` interface so the UI works identically with real hardware or simulation.

**Drivers** own a hardware resource (laser serial port, camera USB). **Clients** handle the TCP protocol to the Red Pitaya.

## Repository Structure

```
piccolo/
├── host/                              # Everything that runs on the PC
│   ├── pyproject.toml                 # Package metadata + dependencies
│   ├── src/piccolo/
│   │   ├── __main__.py                # Entry point: python -m piccolo
│   │   ├── config.py                  # Config loading from YAML
│   │   ├── conversion.py             # Unit conversion (raw ↔ volts, register display)
│   │   ├── piccolo_clients.py         # TCP client classes
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
│       └── test_clients.py
├── firmware/                          # Everything deployed to the Red Pitaya
│   ├── arm/piccolo_rp.py              # Runs on RP ARM core
│   └── fpga/                          # RTL + bitstream
│       ├── rtl/                       # SystemVerilog source
│       └── piccolo.bit.bin            # Compiled bitstream
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

## Communication Protocol

The Red Pitaya hosts four TCP servers:

| Port | Service | Direction | Description |
|---|---|---|---|
| 5000 | Control | PC → RP | Shutdown command |
| 5001 | ADC Stream | RP → PC | Continuous 4-channel ADC waveform data (4096 samples/ch, float32) |
| 5002 | Memory Stream | RP → PC | Droplet measurement data as JSON (intensity, width, area per channel) |
| 5003 | Memory Command | PC → RP | Set FPGA register values via JSON `{"name": ..., "value": ...}` |

## Hardware

| Component | Model | Role |
|---|---|---|
| FPGA board | Red Pitaya STEMlab (4-input variant) | ADC acquisition, real-time droplet detection and sort triggering |
| Laser box | Cobalt Skyra | Multi-line laser source (405, 488, 561, 633 nm) |
| Camera | Basler (USB3, Mono12p, 2048x2048) | Microscope imaging of the microfluidic chip |
| Detectors | SiPM photodetectors (x4) | Fluorescence signal detection, one per channel |
| Sorter | Actuator (driven by FPGA digital output) | Deflects droplets matching gate criteria |
| Microfluidic chip | Custom | Generates and routes droplets through the detection/sort region |

## Dependencies

Core dependencies are managed via `host/pyproject.toml`:

- `dash`, `plotly`, `dash-bootstrap-components` — web UI
- `paramiko`, `scp` — SSH/SCP to Red Pitaya
- `numpy`, `pandas`, `scipy` — data handling and analysis
- `pyserial` — laser box serial communication
- `pyyaml` — configuration loading

Optional (install with `pip install -e ".[camera]"`):

- `opencv-python` — camera frame processing
- `pypylon` — Basler camera SDK (must be installed from [Basler's pylon SDK](https://www.baslerweb.com/en/software/pylon/), not available via pip)
