"""
Unit conversion functions for Piccolo FPGA registers and ADC data.

This is the single source of truth for all raw <-> display conversions.
Used by both instrument controllers and the UI.
"""

import re

# FPGA clock frequency in MHz — the ADC clock on the Red Pitaya STEMlab.
# Width and area registers count in clock cycles at this rate.
FPGA_CLK_MHZ = 125


def raw_to_volts(raw_value, ch, calibration, vp=20.0, adc_max=8192.0):
    """Convert raw ADC value to volts using calibration values."""
    ch_key = f"CH{ch+1}"
    offset, gain = calibration[ch_key]
    return (raw_value - offset) * gain / adc_max * vp


def volts_to_raw(volt_value, ch, calibration, vp=20.0, adc_max=8192.0):
    """Convert volts to raw ADC value using calibration values."""
    ch_key = f"CH{ch+1}"
    offset, gain = calibration[ch_key]
    return int((volt_value * adc_max / vp) / gain + offset)


def convert_registers(raw_registers, calibration):
    """
    Convert all FPGA registers to human-readable display values with units.

    Returns a dict where each value is a tuple: (converted_value, unit_string).
    """
    display_registers = {}

    for name, value in raw_registers.items():
        display_value = value
        unit = ""

        ch_match = re.search(r'\[(\d)\]', name)
        ch = int(ch_match.group(1)) if ch_match else None

        try:
            numeric_value = int(value)

            if ch is not None:
                if 'intensity_thresh' in name:
                    display_value = raw_to_volts(numeric_value, ch, calibration)
                    unit = "V"
                elif 'area_thresh' in name:
                    display_value = raw_to_volts(numeric_value, ch, calibration) / (FPGA_CLK_MHZ * 1000)
                    unit = "V·ms"
                elif 'width_thresh' in name:
                    display_value = numeric_value / (FPGA_CLK_MHZ * 1000)
                    unit = "ms"
            elif 'sort_delay' in name or 'sort_duration' in name or 'camera_trig_delay' in name or 'camera_trig_duration' in name:
                display_value = numeric_value
                unit = "µs"
            elif name == 'droplet_frequency':
                if numeric_value != 0:
                    display_value = int(1e6 / numeric_value)
                    unit = "Hz"
                else:
                    display_value = 0
                unit = "Hz"
        except (ValueError, TypeError):
            display_value = value
            unit = ""

        display_registers[name] = (display_value, unit)

    return display_registers


def convert_display_to_raw(register_name, display_value, calibration):
    """
    Convert a human-readable display value back to a raw FPGA register value.

    This is the reverse of the per-register logic in convert_registers().
    Used by the UI when a user edits a register value.

    Returns the raw integer value to write to the FPGA.
    """
    ch_match = re.search(r'\[(\d)\]', register_name)
    ch = int(ch_match.group(1)) if ch_match else None

    if ch is not None:
        if 'intensity_thresh' in register_name:
            return volts_to_raw(display_value, ch, calibration)
        elif 'area_thresh' in register_name:
            # User enters V·ms, convert to cc×raw
            volts = display_value * FPGA_CLK_MHZ * 1000
            return volts_to_raw(volts, ch, calibration)
        elif 'width_thresh' in register_name:
            # User enters ms, convert to clock cycles
            return int(display_value * FPGA_CLK_MHZ * 1000)
    elif 'sort_delay' in register_name or 'sort_duration' in register_name or 'camera_trig_delay' in register_name or 'camera_trig_duration' in register_name:
        # Already in µs
        return int(display_value)

    # No conversion needed
    return int(display_value)
