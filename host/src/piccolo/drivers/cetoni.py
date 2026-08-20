"""Cetoni Nemesys S syringe-pump driver (QmixSDK).

⚠️⚠️  HARDWARE SAFETY  ⚠️⚠️
This driver commands real syringe pumps. With glass syringes loaded, motion can
shatter them. It is therefore:
  - Never constructed unless pumps are explicitly enabled AND taken out of simulate
    mode (see drivers.pumps.create_pumps — the safety gate).
  - Motion-free on connect(): it opens the bus, looks up pumps, and sets syringe
    parameters/units, but does NOT calibrate or move the piston.
  - `calibrate()` (which DOES move the piston to a reference) is a separate, explicit
    method that is never called automatically and must only be run with syringes
    removed or after explicit operator clearance.

`qmixsdk` is imported lazily inside connect(), so importing this module (or the app)
never touches the SDK or the bus.

NOTE: the QmixSDK method names below follow the standard Python bindings but should be
verified against the installed qmixsdk version before the FIRST real-hardware run.
That first run is intentionally deferred (loaded glass syringes).
"""

import logging

from piccolo.drivers.pumps import (
    PumpController, PumpStatus, DISPENSE, ASPIRATE,
)

logger = logging.getLogger(__name__)


class CetoniPumps(PumpController):
    def __init__(self, syringes, config=None):
        self._specs = {s.name: s for s in syringes}
        self._order = [s.name for s in syringes]
        self._config = config
        self._bus = None
        self._pumps = {}          # name -> qmixsdk Pump handle
        self._connected = False
        # deviceconfig folder exported from the Cetoni Elements config tool
        self._deviceconfig = getattr(config, "cetoni_deviceconfig", None) if config else None
        logger.info("CetoniPumps constructed (NOT connected) for %d pump(s): %s",
                    len(self._order), ", ".join(self._order))

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def connect(self):
        """Open the bus and configure pumps — MOTION-FREE (no calibration/movement)."""
        if self._connected:
            return
        if not self._deviceconfig:
            raise RuntimeError(
                "CetoniPumps.connect() requires a device-config path "
                "(config.cetoni_deviceconfig). Refusing to connect without it."
            )

        # Lazy import: the SDK only exists where it's installed; never load it in dev.
        from qmixsdk import qmixbus, qmixpump

        logger.warning("CetoniPumps: opening bus from %s (motion-free init).",
                       self._deviceconfig)
        self._bus = qmixbus.Bus()
        self._bus.open(self._deviceconfig, "")
        self._bus.start()

        for i, name in enumerate(self._order):
            spec = self._specs[name]
            pump = qmixpump.Pump()
            # Prefer name lookup; fall back to device index.
            try:
                pump.lookup_by_name(name)
            except Exception:
                pump.lookup_by_device_index(i)

            # Units: micro-litres and micro-litres/min.
            pump.set_volume_unit(qmixpump.UnitPrefix.micro, qmixpump.VolumeUnit.litres)
            pump.set_flow_unit(qmixpump.UnitPrefix.micro, qmixpump.VolumeUnit.litres,
                               qmixpump.TimeUnit.per_minute)
            # Syringe geometry (does not move the piston).
            pump.set_syringe_param(spec.inner_diameter_mm, spec.max_piston_stroke_mm)

            # Clear any fault so commands are accepted later. Enabling the drive does
            # NOT move the piston; calibration/movement is deliberately omitted here.
            if pump.is_in_fault_state():
                pump.clear_fault()
            if not pump.is_enabled():
                pump.enable(True)

            self._pumps[name] = pump

        self._connected = True
        logger.warning("CetoniPumps: connected (%d pumps). NOT calibrated — call "
                       "calibrate() explicitly, syringes removed, before real dosing.",
                       len(self._pumps))

    def disconnect(self):
        try:
            self.stop_all()
        finally:
            if self._bus is not None:
                try:
                    self._bus.stop()
                    self._bus.close()
                except Exception as e:
                    logger.error("CetoniPumps: error closing bus: %s", e)
            self._bus = None
            self._pumps = {}
            self._connected = False
            logger.info("CetoniPumps: disconnected.")

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_simulated(self) -> bool:
        return False

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #
    def list_pumps(self):
        return list(self._order)

    def get_status(self, name):
        spec = self._specs[name]
        st = PumpStatus(name=name, connected=self._connected,
                        max_volume_ul=spec.max_volume_ul)
        pump = self._pumps.get(name)
        if pump is not None:
            try:
                st.is_pumping = bool(pump.is_pumping())
                st.flow_ul_min = abs(float(pump.get_flow_is()))
                st.fill_level_ul = float(pump.get_fill_level())
                st.mode = "flow" if st.is_pumping else "idle"
            except Exception as e:
                logger.debug("get_status(%s) read error: %s", name, e)
        return st

    # ------------------------------------------------------------------ #
    # Motion commands
    # ------------------------------------------------------------------ #
    def _require(self, name):
        if not self._connected:
            raise RuntimeError("CetoniPumps not connected.")
        if name not in self._pumps:
            raise ValueError(f"Unknown pump: {name!r}")
        return self._pumps[name]

    @staticmethod
    def _signed(magnitude, direction):
        # QmixSDK convention: positive = dispense, negative = aspirate.
        m = abs(magnitude)
        return -m if direction == ASPIRATE else m

    def set_flow(self, name, flow_ul_min, direction=DISPENSE):
        pump = self._require(name)
        spec = self._specs[name]
        flow = min(abs(flow_ul_min), spec.max_flow_ul_min)
        pump.generate_flow(self._signed(flow, direction))
        logger.info("[cetoni] %s: flow %.1f uL/min %s", name, flow, direction)

    def dose(self, name, volume_ul, flow_ul_min, direction=DISPENSE):
        pump = self._require(name)
        spec = self._specs[name]
        flow = min(abs(flow_ul_min), spec.max_flow_ul_min)
        pump.pump_volume(self._signed(volume_ul, direction), flow)
        logger.info("[cetoni] %s: dose %.1f uL at %.1f uL/min %s",
                    name, abs(volume_ul), flow, direction)

    def set_level(self, name, target_ul, flow_ul_min):
        pump = self._require(name)
        spec = self._specs[name]
        target = max(0.0, min(abs(target_ul), spec.max_volume_ul))
        flow = min(abs(flow_ul_min), spec.max_flow_ul_min)
        pump.set_fill_level(target, flow)   # QmixSDK infers direction from current level
        logger.info("[cetoni] %s: -> level %.1f uL at %.1f uL/min", name, target, flow)

    def fill(self, name, flow_ul_min):
        self.set_level(name, self._specs[name].max_volume_ul, flow_ul_min)

    def empty(self, name, flow_ul_min):
        self.set_level(name, 0.0, flow_ul_min)

    def stop(self, name):
        pump = self._require(name)
        pump.stop_pumping()
        logger.info("[cetoni] %s: stop", name)

    def stop_all(self):
        for name, pump in self._pumps.items():
            try:
                pump.stop_pumping()
            except Exception as e:
                logger.error("[cetoni] stop_all: %s failed: %s", name, e)
        logger.info("[cetoni] STOP ALL pumps")

    # ------------------------------------------------------------------ #
    # DANGER: piston-moving calibration — never called automatically
    # ------------------------------------------------------------------ #
    def calibrate(self, name):
        """Drive the piston to its reference position. MOVES THE SYRINGE.

        Only run with syringes removed (or after explicit operator clearance). This is
        never invoked by connect() or the UI; it exists so calibration is possible when
        deliberately requested.
        """
        pump = self._require(name)
        logger.warning("[cetoni] CALIBRATING %s — piston WILL move.", name)
        pump.calibrate()
