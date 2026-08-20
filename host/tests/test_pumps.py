"""Tests for the simulated pump backend + routines. Never touches hardware.

These exercise SimulatedPumps and RoutinesManager only. The real CetoniPumps driver
is intentionally not imported/instantiated here (it requires qmixsdk + hardware).
"""

import time

from piccolo.drivers.pumps import (
    SimulatedPumps, SyringeSpec, create_pumps, PumpController, DISPENSE, ASPIRATE,
)
from piccolo.pump_routines import RoutinesManager


class _Cfg:
    """Minimal stand-in for PiccoloConfig."""
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_create_pumps_defaults_to_sim():
    p = create_pumps(None)
    assert isinstance(p, PumpController)
    assert p.is_simulated is True


def test_create_pumps_stays_sim_unless_explicitly_enabled():
    # enabled but still simulate -> sim; not enabled -> sim
    assert create_pumps(_Cfg(pumps_enabled=True, pumps_simulate=True, pumps=[])).is_simulated
    assert create_pumps(_Cfg(pumps_enabled=False, pumps_simulate=False, pumps=[])).is_simulated


def test_sim_dispense_decreases_fill():
    p = SimulatedPumps([SyringeSpec(name="a", initial_fill_ul=500, max_flow_ul_min=6000)])
    p.connect()
    try:
        p.set_flow("a", 6000, DISPENSE)   # 100 uL/s
        time.sleep(0.3)
        st = p.get_status("a")
        assert st.is_pumping
        assert st.fill_level_ul < 500
        p.stop("a")
        assert p.get_status("a").is_pumping is False
    finally:
        p.disconnect()


def test_sim_aspirate_increases_fill():
    p = SimulatedPumps([SyringeSpec(name="a", initial_fill_ul=500, max_flow_ul_min=6000)])
    p.connect()
    try:
        p.set_flow("a", 6000, ASPIRATE)
        time.sleep(0.3)
        assert p.get_status("a").fill_level_ul > 500
    finally:
        p.disconnect()


def test_sim_dose_stops_after_target():
    p = SimulatedPumps([SyringeSpec(name="a", initial_fill_ul=500, max_flow_ul_min=60000)])
    p.connect()
    try:
        p.dose("a", 50, 60000, DISPENSE)  # 1000 uL/s -> ~50 uL fast
        time.sleep(0.5)
        st = p.get_status("a")
        assert st.is_pumping is False
        assert 40 <= st.dosed_volume_ul <= 60
    finally:
        p.disconnect()


def test_stop_all():
    p = SimulatedPumps([SyringeSpec(name="a"), SyringeSpec(name="b")])
    p.connect()
    try:
        p.set_flow("a", 100)
        p.set_flow("b", 100)
        p.stop_all()
        assert not p.get_status("a").is_pumping
        assert not p.get_status("b").is_pumping
    finally:
        p.disconnect()


def test_routine_preset_apply_and_persist(tmp_path):
    p = SimulatedPumps([SyringeSpec(name="a")])
    p.connect()
    try:
        path = str(tmp_path / "routines.json")
        rm = RoutinesManager(p, path)
        rm.save_preset("go", {"a": {"action": "flow", "flow_ul_min": 100, "direction": DISPENSE}})
        assert any(r["name"] == "go" for r in rm.list_routines())
        rm.run("go")
        assert p.get_status("a").is_pumping
        # persisted across a reload
        rm2 = RoutinesManager(p, path)
        assert rm2.get("go")["type"] == "preset"
    finally:
        p.disconnect()


def test_routine_sequence_runs_and_aborts(tmp_path):
    p = SimulatedPumps([SyringeSpec(name="a")])
    p.connect()
    try:
        rm = RoutinesManager(p, str(tmp_path / "routines.json"))
        rm.save_sequence("seq", [
            {"action": "flow", "pump": "a", "flow_ul_min": 100, "duration_s": 5},
            {"action": "stop", "pump": "a"},
        ])
        rm.run("seq")
        time.sleep(0.1)
        assert rm.is_running
        assert p.get_status("a").is_pumping
        rm.stop_routine()
        assert not rm.is_running
        assert not p.get_status("a").is_pumping
    finally:
        p.disconnect()


def test_sim_fill_and_empty():
    p = SimulatedPumps([SyringeSpec(name="a", initial_fill_ul=500,
                                    max_volume_ul=1000, max_flow_ul_min=600000)])
    p.connect()
    try:
        p.fill("a", 600000)          # fast aspirate to full
        time.sleep(0.4)
        assert p.get_status("a").fill_level_ul > 900
        p.empty("a", 600000)         # fast dispense to empty
        time.sleep(0.5)
        assert p.get_status("a").fill_level_ul < 100
    finally:
        p.disconnect()


def test_sim_set_level_infers_direction():
    p = SimulatedPumps([SyringeSpec(name="a", initial_fill_ul=200,
                                    max_volume_ul=1000, max_flow_ul_min=600000)])
    p.connect()
    try:
        p.set_level("a", 800, 600000)   # 200 -> 800 requires aspirate
        assert p.get_status("a").direction == ASPIRATE
        time.sleep(0.5)
        assert 780 <= p.get_status("a").fill_level_ul <= 800
    finally:
        p.disconnect()
