"""Syringe-pump abstraction + a simulated backend.

Defines the ``PumpController`` interface the UI/controllers code against, and a
``SimulatedPumps`` backend that models Cetoni Nemesys S syringe pumps entirely in
software — no hardware, no SDK. This is the DEFAULT backend everywhere during
development.

  ⚠️ SAFETY: the real hardware driver (``CetoniPumps`` in cetoni.py) is only ever
  constructed by ``create_pumps()`` when pumps are *explicitly* enabled AND not in
  simulate mode. With glass syringes loaded, keep pumps simulated until hardware
  connection is explicitly cleared.
"""

import time
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger(__name__)

# Direction of piston travel.
DISPENSE = "dispense"   # push liquid out — fill level decreases
ASPIRATE = "aspirate"   # draw liquid in — fill level increases


@dataclass
class SyringeSpec:
    """Static description of a pump + its loaded syringe."""
    name: str
    inner_diameter_mm: float = 7.28      # Nemesys S default-ish; from device config
    max_piston_stroke_mm: float = 60.0   # syringe piston stroke (for QmixSDK syringe param)
    max_volume_ul: float = 1000.0        # syringe capacity
    max_flow_ul_min: float = 6000.0      # safety cap for the UI
    initial_fill_ul: float = 500.0


@dataclass
class PumpStatus:
    """Live state of one pump (what the UI displays)."""
    name: str
    connected: bool = False
    is_pumping: bool = False
    mode: str = "idle"                   # idle | flow | dose | stopped
    direction: Optional[str] = None      # dispense | aspirate | None
    flow_ul_min: float = 0.0             # current flow magnitude
    fill_level_ul: float = 0.0
    max_volume_ul: float = 0.0
    target_volume_ul: float = 0.0        # for dose mode
    dosed_volume_ul: float = 0.0         # progress within a dose
    target_level_ul: float = 0.0         # for level (fill/empty) mode

    def as_dict(self):
        return asdict(self)


class PumpController(ABC):
    """Interface for a bank of syringe pumps (real or simulated)."""

    # --- lifecycle ---
    @abstractmethod
    def connect(self):
        """Connect to the pump bank (no-op for the simulator)."""
        ...

    @abstractmethod
    def disconnect(self):
        """Disconnect / release the pump bank."""
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        ...

    @property
    @abstractmethod
    def is_simulated(self) -> bool:
        ...

    # --- introspection ---
    @abstractmethod
    def list_pumps(self) -> list:
        """Return the ordered list of pump names."""
        ...

    @abstractmethod
    def get_status(self, name: str) -> PumpStatus:
        ...

    def get_all_status(self) -> dict:
        return {name: self.get_status(name) for name in self.list_pumps()}

    # --- motion commands ---
    @abstractmethod
    def set_flow(self, name: str, flow_ul_min: float, direction: str = DISPENSE):
        """Run a pump continuously at ``flow_ul_min`` until stopped."""
        ...

    @abstractmethod
    def dose(self, name: str, volume_ul: float, flow_ul_min: float, direction: str = DISPENSE):
        """Move a fixed ``volume_ul`` at ``flow_ul_min`` then stop."""
        ...

    @abstractmethod
    def set_level(self, name: str, target_ul: float, flow_ul_min: float):
        """Move to a target fill level; direction is inferred from the current level."""
        ...

    @abstractmethod
    def fill(self, name: str, flow_ul_min: float):
        """Aspirate until the syringe is full."""
        ...

    @abstractmethod
    def empty(self, name: str, flow_ul_min: float):
        """Dispense until the syringe is empty."""
        ...

    @abstractmethod
    def stop(self, name: str):
        """Stop one pump."""
        ...

    @abstractmethod
    def stop_all(self):
        """Emergency stop: halt every pump immediately."""
        ...


class SimulatedPumps(PumpController):
    """In-software syringe pumps. No hardware, no SDK — safe for development.

    Models fill level over time from the commanded flow so the UI shows realistic
    motion, fill-level changes, and dose completion.
    """

    def __init__(self, syringes=None, update_hz: float = 20.0):
        if syringes is None:
            # Default bank: 4 Nemesys S. Trim/edit via config.
            syringes = [SyringeSpec(name=f"pump{i}") for i in range(4)]
        self._specs = {s.name: s for s in syringes}
        self._order = [s.name for s in syringes]

        self._status = {}
        for s in syringes:
            self._status[s.name] = PumpStatus(
                name=s.name,
                connected=True,          # sim is always "connected"
                fill_level_ul=s.initial_fill_ul,
                max_volume_ul=s.max_volume_ul,
            )

        self._lock = threading.Lock()
        self._period = 1.0 / update_hz
        self._running = False
        self._thread = None
        logger.info("SimulatedPumps initialized with %d pump(s): %s",
                    len(self._order), ", ".join(self._order))

    # --- lifecycle ---
    def connect(self):
        if self._running:
            return
        self._running = True
        self._last_t = time.time()
        self._thread = threading.Thread(target=self._run, name="sim-pumps", daemon=True)
        self._thread.start()
        logger.info("SimulatedPumps: motion model started.")

    def disconnect(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self.stop_all()

    @property
    def is_connected(self) -> bool:
        return self._running

    @property
    def is_simulated(self) -> bool:
        return True

    # --- introspection ---
    def list_pumps(self):
        return list(self._order)

    def get_status(self, name):
        with self._lock:
            # return a copy so callers can't mutate internal state
            return PumpStatus(**self._status[name].as_dict())

    # --- motion commands ---
    def _check(self, name):
        if name not in self._status:
            raise ValueError(f"Unknown pump: {name!r}")

    def set_flow(self, name, flow_ul_min, direction=DISPENSE):
        self._check(name)
        spec = self._specs[name]
        flow = max(0.0, min(abs(flow_ul_min), spec.max_flow_ul_min))
        with self._lock:
            st = self._status[name]
            st.mode = "flow"
            st.direction = direction
            st.flow_ul_min = flow
            st.target_volume_ul = 0.0
            st.dosed_volume_ul = 0.0
            st.is_pumping = flow > 0
        logger.info("[sim] %s: flow %.1f uL/min %s", name, flow, direction)

    def dose(self, name, volume_ul, flow_ul_min, direction=DISPENSE):
        self._check(name)
        spec = self._specs[name]
        flow = max(0.0, min(abs(flow_ul_min), spec.max_flow_ul_min))
        with self._lock:
            st = self._status[name]
            st.mode = "dose"
            st.direction = direction
            st.flow_ul_min = flow
            st.target_volume_ul = abs(volume_ul)
            st.dosed_volume_ul = 0.0
            st.is_pumping = flow > 0 and abs(volume_ul) > 0
        logger.info("[sim] %s: dose %.1f uL at %.1f uL/min %s",
                    name, abs(volume_ul), flow, direction)

    def set_level(self, name, target_ul, flow_ul_min):
        self._check(name)
        spec = self._specs[name]
        target = max(0.0, min(abs(target_ul), spec.max_volume_ul))
        flow = max(0.0, min(abs(flow_ul_min), spec.max_flow_ul_min))
        with self._lock:
            st = self._status[name]
            if flow <= 0 or abs(target - st.fill_level_ul) < 1e-9:
                st.is_pumping = False
                st.mode = "idle"
                st.flow_ul_min = 0.0
                return
            st.mode = "level"
            st.direction = ASPIRATE if target > st.fill_level_ul else DISPENSE
            st.flow_ul_min = flow
            st.target_level_ul = target
            st.is_pumping = True
        logger.info("[sim] %s: -> level %.1f uL at %.1f uL/min", name, target, flow)

    def fill(self, name, flow_ul_min):
        self._check(name)
        self.set_level(name, self._specs[name].max_volume_ul, flow_ul_min)

    def empty(self, name, flow_ul_min):
        self._check(name)
        self.set_level(name, 0.0, flow_ul_min)

    def stop(self, name):
        self._check(name)
        with self._lock:
            st = self._status[name]
            st.is_pumping = False
            st.mode = "stopped"
            st.flow_ul_min = 0.0
        logger.info("[sim] %s: stop", name)

    def stop_all(self):
        with self._lock:
            for st in self._status.values():
                st.is_pumping = False
                st.mode = "stopped"
                st.flow_ul_min = 0.0
        logger.info("[sim] STOP ALL pumps")

    # --- background motion model ---
    def _run(self):
        while self._running:
            now = time.time()
            dt = now - self._last_t
            self._last_t = now
            with self._lock:
                for st in self._status.values():
                    if not st.is_pumping or st.flow_ul_min <= 0:
                        continue
                    moved = st.flow_ul_min / 60.0 * dt   # uL this tick
                    spec = self._specs[st.name]

                    if st.mode == "dose":
                        moved = min(moved, st.target_volume_ul - st.dosed_volume_ul)
                    elif st.mode == "level":
                        moved = min(moved, abs(st.target_level_ul - st.fill_level_ul))

                    if st.direction == ASPIRATE:
                        new_fill = min(spec.max_volume_ul, st.fill_level_ul + moved)
                    else:  # dispense
                        new_fill = max(0.0, st.fill_level_ul - moved)
                    moved = abs(new_fill - st.fill_level_ul)
                    st.fill_level_ul = new_fill

                    if st.mode == "dose":
                        st.dosed_volume_ul += moved
                        if st.dosed_volume_ul >= st.target_volume_ul - 1e-9:
                            st.is_pumping = False
                            st.mode = "idle"
                            st.flow_ul_min = 0.0
                    elif st.mode == "level":
                        if abs(st.fill_level_ul - st.target_level_ul) < 1e-6:
                            st.is_pumping = False
                            st.mode = "idle"
                            st.flow_ul_min = 0.0

                    # Reached a syringe limit -> stop (sim safety mirror)
                    if st.fill_level_ul <= 0.0 or st.fill_level_ul >= spec.max_volume_ul:
                        if st.is_pumping:
                            st.is_pumping = False
                            st.mode = "idle"
                            st.flow_ul_min = 0.0
            time.sleep(self._period)


def create_pumps(config=None) -> PumpController:
    """Factory that chooses a pump backend from config.

    Returns SimulatedPumps unless pumps are BOTH explicitly enabled and explicitly
    taken out of simulate mode. This is the safety gate: the real CetoniPumps driver
    is imported lazily and only when the operator has cleared hardware connection.
    """
    pumps_enabled = bool(getattr(config, "pumps_enabled", False)) if config else False
    pumps_simulate = bool(getattr(config, "pumps_simulate", True)) if config else True
    syringes = _syringes_from_config(config)

    if pumps_enabled and not pumps_simulate:
        # Lazy import so qmixsdk is never loaded unless we truly connect to hardware.
        logger.warning("Pumps: HARDWARE mode requested — constructing CetoniPumps.")
        from piccolo.drivers.cetoni import CetoniPumps
        return CetoniPumps(syringes=syringes, config=config)

    logger.info("Pumps: using SimulatedPumps (safe, no hardware).")
    return SimulatedPumps(syringes=syringes)


def _syringes_from_config(config):
    """Build SyringeSpec list from config.pumps (list of dicts), or a 4-pump default."""
    raw = getattr(config, "pumps", None) if config else None
    if not raw:
        return [SyringeSpec(name=f"pump{i}") for i in range(4)]
    specs = []
    for i, p in enumerate(raw):
        specs.append(SyringeSpec(
            name=p.get("name", f"pump{i}"),
            inner_diameter_mm=p.get("inner_diameter_mm", 7.28),
            max_piston_stroke_mm=p.get("max_piston_stroke_mm", 60.0),
            max_volume_ul=p.get("max_volume_ul", 1000.0),
            max_flow_ul_min=p.get("max_flow_ul_min", 6000.0),
            initial_fill_ul=p.get("initial_fill_ul", 500.0),
        ))
    return specs
