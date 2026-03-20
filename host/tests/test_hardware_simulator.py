"""Tests for piccolo.controllers.hardware_simulator — signal generation and droplet detection."""

import time

import numpy as np
import pandas as pd
import pytest

from piccolo.controllers.hardware_simulator import HardwareSimulator
from piccolo.controllers.controller import InstrumentController


@pytest.fixture
def sim():
    """Create a quiet simulator for testing."""
    s = HardwareSimulator(verbose=False, very_verbose=False)
    yield s
    if s._running:
        s.stop()


class TestSimulatorInit:
    def test_is_instrument_controller(self, sim):
        assert isinstance(sim, InstrumentController)

    def test_initial_state(self, sim):
        assert sim._running is False
        assert isinstance(sim.droplet_data, pd.DataFrame)
        assert len(sim.droplet_data) == 0
        assert sim.laser_box is None

    def test_fpga_registers_populated(self, sim):
        regs = sim.get_fpga_registers()
        assert "sort_enable" in regs
        assert "detection_channel" in regs
        assert "min_intensity_thresh[0]" in regs
        assert "high_area_thresh[3]" in regs

    def test_calibration_values_present(self, sim):
        assert "CH1" in sim.calibration_values
        assert "CH4" in sim.calibration_values
        assert len(sim.calibration_values["CH1"]) == 2


class TestSignalGeneration:
    def test_start_stop(self, sim):
        sim.start()
        assert sim._running is True
        time.sleep(0.3)
        sim.stop()
        assert sim._running is False

    def test_generates_adc_data(self, sim):
        sim.start()
        time.sleep(0.5)
        sim.stop()
        assert len(sim.adc1_data) == 4096
        assert len(sim.adc2_data) == 4096
        assert len(sim.adc3_data) == 4096
        assert len(sim.adc4_data) == 4096

    def test_generates_droplet_data(self, sim):
        sim.start()
        time.sleep(0.5)
        sim.stop()
        assert len(sim.droplet_data) > 0
        # Should have intensity, width, area columns for all 4 channels
        for ch in range(4):
            assert f"cur_droplet_intensity[{ch}]" in sim.droplet_data.columns
            assert f"cur_droplet_width_ms[{ch}]" in sim.droplet_data.columns
            assert f"cur_droplet_area_vms[{ch}]" in sim.droplet_data.columns

    def test_droplet_counter_increments(self, sim):
        sim.start()
        time.sleep(0.5)
        sim.stop()
        assert sim.fpga_registers["droplet_counter"] > 0

    def test_buffer_size_respected(self, sim):
        sim.buffer_size = 50
        sim.start()
        time.sleep(1.0)
        sim.stop()
        assert len(sim.droplet_data) <= 50


class TestDetectionAndGating:
    def test_set_detection_threshold(self, sim):
        sim.set_detection_threshold(0.1, ch=2)
        assert sim.threshold == 0.1
        assert sim.fpga_registers["detection_channel"] == 2

    def test_set_memory_variable(self, sim):
        sim.set_memory_variable("sort_enable", 1)
        assert sim.fpga_registers["sort_enable"] == 1

    def test_enable_detection(self, sim):
        sim.enable_detection(True)
        assert sim.fpga_registers["detection_enable"] == 1
        sim.enable_detection(False)
        assert sim.fpga_registers["detection_enable"] == 0

    def test_enable_sorter(self, sim):
        sim.enable_sorter(True)
        assert sim.fpga_registers["sort_enable"] == 1
        sim.enable_sorter(False)
        assert sim.fpga_registers["sort_enable"] == 0

    def test_set_gate_limits(self, sim):
        sort_keys = ["cur_droplet_intensity_v[0]", "cur_droplet_width_ms[1]"]
        limits = {"x0": [0.1], "y0": [0.5], "x1": [1.0], "y1": [2.0]}
        gates = sim.set_gate_limits(sort_keys, limits)
        assert "low_intensity_thresh[0]" in gates
        assert "high_intensity_thresh[0]" in gates
        assert "low_width_thresh[1]" in gates
        assert "high_width_thresh[1]" in gates

    def test_get_sort_gates_empty_initially(self, sim):
        assert sim.get_sort_gates() == {}

    def test_get_sort_gates_after_set(self, sim):
        sort_keys = ["cur_droplet_intensity_v[0]", "cur_droplet_width_ms[0]"]
        limits = {"x0": [0.1], "y0": [0.5], "x1": [1.0], "y1": [2.0]}
        sim.set_gate_limits(sort_keys, limits)
        gates = sim.get_sort_gates()
        assert len(gates) > 0


class TestConversion:
    def test_convert_raw_to_volts(self, sim):
        v = sim.convert_raw_to_volts(4096, 0)
        assert isinstance(v, float)
        assert v > 0

    def test_convert_volts_to_raw(self, sim):
        raw = sim.convert_volts_to_raw(1.0, 0)
        assert isinstance(raw, int)

    def test_get_fpga_registers_converted(self, sim):
        converted = sim.get_fpga_registers_converted()
        assert isinstance(converted, dict)
        # Intensity thresholds should have units
        val, unit = converted["min_intensity_thresh[0]"]
        assert unit == "V"


class TestLaserStubs:
    def test_laser_on_state_no_error(self, sim):
        sim.set_laser_on_state("405", True)
        sim.set_laser_on_state("405", False)

    def test_laser_power_no_error(self, sim):
        sim.set_laser_power("488", 10)


class TestDataLogging:
    def test_clear_droplet_data(self, sim):
        sim.start()
        time.sleep(0.3)
        sim.stop()
        assert len(sim.droplet_data) > 0
        sim.clear_droplet_data()
        assert len(sim.droplet_data) == 0

    def test_save_droplet_data_log(self, sim, tmp_path):
        sim.start()
        time.sleep(0.3)
        sim.stop()
        filepath = tmp_path / "test_droplet.csv"
        sim.save_droplet_data_log(str(filepath))
        assert filepath.exists()
        assert filepath.stat().st_size > 0

    def test_save_adc_log(self, sim, tmp_path):
        sim.start()
        time.sleep(0.3)
        sim.stop()
        filepath = tmp_path / "test_adc.csv"
        sim.save_adc_log(str(filepath))
        assert filepath.exists()
        assert filepath.stat().st_size > 0
