"""Pump routines: named settings presets and timed multi-step sequences.

A routine is stored as JSON and is one of:
  - preset:   {"type": "preset", "pumps": {pump_name: {action, ...}}}
                applied all at once (set flow / dose / stop per pump)
  - sequence: {"type": "sequence", "steps": [ {action, pump?, ..., duration_s?} ]}
                executed in order by a background sequencer thread (abortable)

Step / preset actions: "flow" (flow_ul_min, direction), "dose" (volume_ul,
flow_ul_min, direction), "stop" (pump or all), "wait" (duration_s only).

Runs entirely against the injected PumpController — which is the simulated backend in
development, so routines are safe to build and run without touching hardware.
"""

import os
import json
import logging
import threading

from piccolo.drivers.pumps import DISPENSE

logger = logging.getLogger(__name__)


class RoutinesManager:
    def __init__(self, pumps, path=None):
        self.pumps = pumps
        self.path = path or "pump_routines.json"
        self._routines = {}
        self._seq_thread = None
        self._abort = threading.Event()
        self._running_name = None
        self.load()

    # ---------------- persistence ----------------
    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    self._routines = json.load(f).get("routines", {})
                logger.info("Loaded %d pump routine(s) from %s",
                            len(self._routines), self.path)
            except Exception as e:
                logger.error("Failed to load routines from %s: %s", self.path, e)
                self._routines = {}
        return self._routines

    def _save_file(self):
        try:
            with open(self.path, "w") as f:
                json.dump({"routines": self._routines}, f, indent=2)
        except Exception as e:
            logger.error("Failed to save routines to %s: %s", self.path, e)

    # ---------------- CRUD ----------------
    def list_routines(self):
        return [{"name": n, "type": r.get("type")} for n, r in self._routines.items()]

    def get(self, name):
        return self._routines.get(name)

    def save_preset(self, name, pump_settings: dict):
        self._routines[name] = {"type": "preset", "pumps": pump_settings}
        self._save_file()
        logger.info("Saved preset routine %r (%d pumps)", name, len(pump_settings))

    def save_sequence(self, name, steps: list):
        self._routines[name] = {"type": "sequence", "steps": steps}
        self._save_file()
        logger.info("Saved sequence routine %r (%d steps)", name, len(steps))

    def delete(self, name):
        if self._routines.pop(name, None) is not None:
            self._save_file()
            logger.info("Deleted routine %r", name)

    # ---------------- execution ----------------
    @property
    def is_running(self):
        return self._seq_thread is not None and self._seq_thread.is_alive()

    @property
    def running_name(self):
        return self._running_name

    def run(self, name):
        r = self._routines.get(name)
        if not r:
            raise ValueError(f"Unknown routine: {name!r}")
        if r.get("type") == "preset":
            self._apply_preset(r)
        elif r.get("type") == "sequence":
            self.stop_routine()          # cancel anything already running
            self._abort.clear()
            self._running_name = name
            self._seq_thread = threading.Thread(
                target=self._run_sequence, args=(name, r.get("steps", [])),
                name=f"routine-{name}", daemon=True)
            self._seq_thread.start()
        else:
            raise ValueError(f"Unknown routine type for {name!r}: {r.get('type')}")

    def _do_action(self, step):
        action = step.get("action")
        pump = step.get("pump")
        direction = step.get("direction", DISPENSE)
        if action == "flow":
            self.pumps.set_flow(pump, step["flow_ul_min"], direction)
        elif action == "dose":
            self.pumps.dose(pump, step["volume_ul"], step["flow_ul_min"], direction)
        elif action == "stop":
            if pump:
                self.pumps.stop(pump)
            else:
                self.pumps.stop_all()
        elif action == "wait":
            pass
        else:
            logger.warning("Routine step: unknown action %r (skipped)", action)

    def _apply_preset(self, r):
        for pump, s in r.get("pumps", {}).items():
            self._do_action({**s, "pump": pump})
        logger.info("Applied preset routine.")

    def _run_sequence(self, name, steps):
        logger.info("Running sequence routine %r (%d steps)", name, len(steps))
        for i, step in enumerate(steps):
            if self._abort.is_set():
                logger.info("Routine %r aborted at step %d", name, i)
                break
            self._do_action(step)
            dur = step.get("duration_s")
            if dur:
                # interruptible sleep — wakes immediately on abort
                if self._abort.wait(timeout=float(dur)):
                    logger.info("Routine %r aborted during step %d wait", name, i)
                    break
        self._running_name = None
        logger.info("Sequence routine %r finished.", name)

    def stop_routine(self):
        """Abort a running sequence and stop all pumps."""
        self._abort.set()
        if self._seq_thread:
            self._seq_thread.join(timeout=2.0)
            self._seq_thread = None
        self._running_name = None
        self.pumps.stop_all()
