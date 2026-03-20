# Piccolo

Piccolo is a fluorescence-activated droplet sorting (FADS) instrument control system. It provides real-time detection, analysis, and sorting of microfluidic droplets based on multi-channel fluorescence signals.

## Screenshot

![social_preview](/social_preview.png?raw=true)

## Quickstart

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run the UI:
   ```
   python piccolo_ui.py
   ```

   The web interface launches at `http://127.0.0.1:8050/`.

3. To run without hardware (simulation mode), set `simulate = True` in `piccolo_ui.py`.

## Architecture

The system is organized into three layers: FPGA, instrument, and UI.

```
┌──────────────────────────────────────────────────────┐
│  piccolo_ui.py  (Dash/Plotly web UI on host PC)      │
│  - Scatter plots, signal viewer, camera feed         │
│  - Laser controls, gating, FPGA register editor      │
├──────────────────────────────────────────────────────┤
│  piccolo_instrument.py  (Instrument controller)      │
│  - Manages Red Pitaya connection (SSH/SCP)           │
│  - Runs TCP clients for data streaming & commands    │
│  - Controls Cobalt Skyra laser box via serial        │
│  piccolo_clients.py  (TCP client implementations)    │
│  cobalt_skyra.py  (Laser serial driver)              │
├──────────────────────────────────────────────────────┤
│  redpitaya/piccolo_rp.py  (Runs on Red Pitaya ARM)   │
│  - Memory-maps FPGA registers for read/write         │
│  - Exposes TCP servers for remote access              │
│  - Streams ADC waveforms and droplet measurements    │
├──────────────────────────────────────────────────────┤
│  fpga/  (FPGA bitstream + RTL)                       │
│  - Real-time droplet detection on 4 ADC channels     │
│  - Threshold, width, and area gating per channel     │
│  - Sort trigger output                               │
└──────────────────────────────────────────────────────┘
```

## File Overview

| File | Description |
|---|---|
| `piccolo_ui.py` | Dash web application — plots, controls, camera feed, FPGA register editor |
| `piccolo_instrument.py` | Instrument class — connects to Red Pitaya, manages clients, controls lasers, handles unit conversion |
| `piccolo_instrument_sim.py` | Simulation mode — generates synthetic droplet signals for offline development |
| `piccolo_clients.py` | TCP client classes for communicating with the Red Pitaya servers |
| `cobalt_skyra.py` | Serial driver for the Cobalt Skyra multi-laser box |
| `redpitaya/piccolo_rp.py` | Runs on the Red Pitaya — memory-maps FPGA registers and hosts TCP servers |
| `redpitaya/piccolo_mmap.json` | FPGA register map — defines variable names, addresses, data types, and defaults |
| `fpga/rtl/` | SystemVerilog RTL source for the FADS detection and sorting logic |
| `fpga/piccolo.bit.bin` | Compiled FPGA bitstream, loaded onto the Red Pitaya at startup |
| `laser_config.json` | Laser box configuration — COM port, serial number, wavelength-to-channel mapping |
| `redpitaya/rp_login.json` | Red Pitaya SSH credentials (IP, username, password) |
| `assets/` | CSS stylesheets for the Dash UI |

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

Key Python packages (see `requirements.txt` for full list):

- `dash`, `plotly`, `dash-bootstrap-components` — web UI
- `paramiko`, `scp` — SSH/SCP to Red Pitaya
- `pypylon` — Basler camera SDK
- `opencv-python` — camera frame processing
- `numpy`, `pandas`, `scipy` — data handling and analysis
- `pyserial` — laser box serial communication