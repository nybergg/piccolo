"""Tests for piccolo.conversion — raw/volts round-trips and register conversion."""

import pytest
from piccolo.conversion import raw_to_volts, volts_to_raw, convert_registers, convert_display_to_raw


# Default calibration used across tests
CAL = {
    "CH1": [-10, 1.0],
    "CH2": [-10, 1.0],
    "CH3": [-10, 1.0],
    "CH4": [-10, 1.0],
}


class TestRawToVolts:
    def test_zero_raw_gives_negative_volts(self):
        # raw=0, offset=-10 → (0 - (-10)) * 1.0 / 8192 * 20 = 0.0244 V
        v = raw_to_volts(0, 0, CAL)
        assert v == pytest.approx(10 * 20 / 8192, rel=1e-6)

    def test_known_value(self):
        # raw=4096, ch=0 → (4096 - (-10)) * 1.0 / 8192 * 20
        v = raw_to_volts(4096, 0, CAL)
        expected = (4096 + 10) * 1.0 / 8192.0 * 20.0
        assert v == pytest.approx(expected, rel=1e-6)

    def test_different_channels_same_cal(self):
        # All channels have the same calibration, so results should match
        for ch in range(4):
            assert raw_to_volts(100, ch, CAL) == pytest.approx(raw_to_volts(100, 0, CAL))

    def test_custom_calibration(self):
        custom_cal = {"CH1": [0, 2.0]}
        # raw=8192 → (8192 - 0) * 2.0 / 8192 * 20 = 40.0
        v = raw_to_volts(8192, 0, custom_cal)
        assert v == pytest.approx(40.0, rel=1e-6)


class TestVoltsToRaw:
    def test_round_trip(self):
        """Converting raw→volts→raw should return the original value."""
        for raw in [0, 100, 4096, 8191]:
            volts = raw_to_volts(raw, 0, CAL)
            recovered = volts_to_raw(volts, 0, CAL)
            assert recovered == raw, f"Round-trip failed for raw={raw}"

    def test_round_trip_all_channels(self):
        for ch in range(4):
            raw = 2048
            volts = raw_to_volts(raw, ch, CAL)
            recovered = volts_to_raw(volts, ch, CAL)
            assert recovered == raw


class TestConvertRegisters:
    def test_intensity_thresh_converted_to_volts(self):
        regs = {"min_intensity_thresh[0]": 100}
        result = convert_registers(regs, CAL)
        value, unit = result["min_intensity_thresh[0]"]
        assert unit == "V"
        assert value == pytest.approx(raw_to_volts(100, 0, CAL), rel=1e-6)

    def test_width_thresh_converted_to_ms(self):
        regs = {"min_width_thresh[1]": 5000}
        result = convert_registers(regs, CAL)
        value, unit = result["min_width_thresh[1]"]
        assert unit == "ms"
        assert value == pytest.approx(5.0)

    def test_area_thresh_converted_to_vms(self):
        regs = {"low_area_thresh[2]": 1000}
        result = convert_registers(regs, CAL)
        value, unit = result["low_area_thresh[2]"]
        assert unit == "V·ms"
        assert value == pytest.approx(raw_to_volts(1000, 2, CAL) / 1000.0, rel=1e-6)

    def test_sort_delay_converted_to_ms(self):
        regs = {"sort_delay": 2500}
        result = convert_registers(regs, CAL)
        value, unit = result["sort_delay"]
        assert unit == "ms"
        assert value == pytest.approx(2.5)

    def test_droplet_frequency_zero(self):
        regs = {"droplet_frequency": 0}
        result = convert_registers(regs, CAL)
        value, unit = result["droplet_frequency"]
        assert unit == "Hz"
        assert value == 0

    def test_droplet_frequency_nonzero(self):
        regs = {"droplet_frequency": 1000}  # 1e6/1000 = 1000 Hz
        result = convert_registers(regs, CAL)
        value, unit = result["droplet_frequency"]
        assert unit == "Hz"
        assert value == 1000

    def test_passthrough_register(self):
        regs = {"sort_enable": 1}
        result = convert_registers(regs, CAL)
        value, unit = result["sort_enable"]
        assert value == 1
        assert unit == ""


class TestConvertDisplayToRaw:
    def test_intensity_round_trip(self):
        """display_to_raw should reverse convert_registers for intensity."""
        raw_val = 500
        regs = {f"min_intensity_thresh[0]": raw_val}
        converted = convert_registers(regs, CAL)
        display_val, _ = converted["min_intensity_thresh[0]"]
        recovered = convert_display_to_raw("min_intensity_thresh[0]", display_val, CAL)
        assert recovered == raw_val

    def test_width_round_trip(self):
        raw_val = 12500  # 12.5 ms
        regs = {"low_width_thresh[1]": raw_val}
        converted = convert_registers(regs, CAL)
        display_val, _ = converted["low_width_thresh[1]"]
        recovered = convert_display_to_raw("low_width_thresh[1]", display_val, CAL)
        assert recovered == raw_val

    def test_sort_delay_round_trip(self):
        raw_val = 3000  # 3.0 ms
        regs = {"sort_delay": raw_val}
        converted = convert_registers(regs, CAL)
        display_val, _ = converted["sort_delay"]
        recovered = convert_display_to_raw("sort_delay", display_val, CAL)
        assert recovered == raw_val

    def test_passthrough_value(self):
        recovered = convert_display_to_raw("sort_enable", 1, CAL)
        assert recovered == 1
