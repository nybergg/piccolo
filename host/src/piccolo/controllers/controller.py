"""
InstrumentController — abstract base class for Piccolo instrument controllers.

Defines the interface that the UI codes against, plus shared implementations
for conversion, gating, detection, and data logging. Subclasses only need to
implement hardware-specific methods (set_memory_variable, start, stop, laser).
"""

import logging
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from piccolo.conversion import raw_to_volts, volts_to_raw, convert_registers

logger = logging.getLogger(__name__)


class InstrumentController(ABC):

    # --- Abstract methods (subclass must implement) ---

    @abstractmethod
    def set_memory_variable(self, name: str, value: int):
        """Write a variable to FPGA memory (or simulate doing so)."""
        ...

    @abstractmethod
    def start(self):
        """Start the instrument (connect hardware or begin simulation)."""
        ...

    @abstractmethod
    def stop(self):
        """Stop the instrument and clean up resources."""
        ...

    @abstractmethod
    def set_laser_on_state(self, name: str, state: bool):
        """Turn a laser on or off."""
        ...

    @abstractmethod
    def set_laser_power(self, name: str, power_mw: float):
        """Set laser power in milliwatts."""
        ...

    # --- Shared implementations ---

    def get_fpga_registers(self) -> dict:
        """Return the cached dictionary of FPGA register values."""
        return self.fpga_registers

    def get_fpga_registers_converted(self) -> dict:
        """Return FPGA registers with human-readable values and units."""
        return convert_registers(self.get_fpga_registers(), self.calibration_values)

    def convert_raw_to_volts(self, raw_value, ch):
        """Convert raw ADC value to volts using calibration values."""
        return raw_to_volts(raw_value, ch, self.calibration_values)

    def convert_volts_to_raw(self, volt_value, ch):
        """Convert volts to raw ADC value using calibration values."""
        return volts_to_raw(volt_value, ch, self.calibration_values)

    def enable_sorter(self, enable: bool):
        """Enable or disable the droplet sorter."""
        self.set_memory_variable("sort_enable", 1 if enable else 0)
        status = "enabled" if enable else "disabled"
        logger.info("Sorter has been %s.", status)

    def enable_detection(self, enable: bool):
        """Enable or disable droplet detection."""
        self.set_memory_variable("detection_enable", 1 if enable else 0)
        status = "enabled" if enable else "disabled"
        logger.info("Droplet detection has been %s.", status)

    def set_detection_threshold(self, thresh, ch=0):
        """Set the detection threshold voltage and channel."""
        logger.debug("Setting detection channel as %s", ch)
        logger.debug("Setting detection threshold to %s", thresh)
        thresh_key = f"min_intensity_thresh[{ch}]"
        thresh_raw = self.convert_volts_to_raw(thresh, ch)
        self.set_memory_variable("detection_channel", ch)
        self.set_memory_variable(thresh_key, int(thresh_raw))

    def set_gate_limits(self, sort_keys, limits):
        """Set sort gate limits from UI box selection."""
        logger.debug("Received gate limits to set: %s", limits)

        if not hasattr(self, 'sort_gates'):
            self.sort_gates = {}

        for i, key in enumerate(sort_keys):
            ch = int(key[key.find('[') + 1:key.find(']')])

            low_coord = 'x0' if i == 0 else 'y0'
            high_coord = 'x1' if i == 0 else 'y1'

            low_val = limits[low_coord]
            high_val = limits[high_coord]
            if isinstance(low_val, list):
                low_val = low_val[0]
            if isinstance(high_val, list):
                high_val = high_val[0]

            # Convert display units to raw FPGA values
            if "_vms" in key:
                from piccolo.conversion import FPGA_CLK_MHZ
                low_val = int(self.convert_volts_to_raw(low_val, ch) * FPGA_CLK_MHZ * 1000)
                high_val = int(self.convert_volts_to_raw(high_val, ch) * FPGA_CLK_MHZ * 1000)
            elif "_ms" in key:
                from piccolo.conversion import FPGA_CLK_MHZ
                low_val = int(low_val * FPGA_CLK_MHZ * 1000)
                high_val = int(high_val * FPGA_CLK_MHZ * 1000)
            elif "_v" in key:
                low_val = self.convert_volts_to_raw(low_val, ch)
                high_val = self.convert_volts_to_raw(high_val, ch)

            if "intensity" in key:
                param = "intensity"
            elif "width" in key:
                param = "width"
            elif "area" in key:
                param = "area"
            else:
                raise ValueError(f"Unrecognized key: {key}")

            self.sort_gates[f"low_{param}_thresh[{ch}]"] = low_val
            self.sort_gates[f"high_{param}_thresh[{ch}]"] = high_val

        logger.debug("Setting cumulative sort gates: %s", self.sort_gates)

        for var, val in self.sort_gates.items():
            self.set_memory_variable(var, int(val))

        return self.sort_gates

    def get_sort_gates(self):
        """Returns the currently configured sort gates."""
        if hasattr(self, 'sort_gates'):
            return self.sort_gates
        return {}

    def save_droplet_data_log(self, filename="droplet_log.csv"):
        """Save droplet data buffer to CSV."""
        self.droplet_data.to_csv(filename, index=False)

    def save_adc_log(self, filename="adc_log.csv"):
        """Save ADC data to CSV."""
        time_data = np.linspace(0, 50, 4096)
        adc_data = {
            'time': time_data,
            'adc1': self.adc1_data,
            'adc2': self.adc2_data,
            'adc3': self.adc3_data,
            'adc4': self.adc4_data,
        }
        df = pd.DataFrame({k: v for k, v in adc_data.items() if v is not None and len(v) == len(time_data)})
        df.to_csv(filename, index=False)

    def clear_droplet_data(self):
        """Clears the internal droplet data buffer."""
        logger.debug("Clearing droplet data buffer.")
        self.droplet_data = pd.DataFrame()
