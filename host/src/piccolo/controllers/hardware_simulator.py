"""
HardwareSimulator — simulates Piccolo hardware for offline development.

Generates synthetic droplet signals and analyzes them, providing the same
interface as HardwareController without requiring any physical hardware.
"""

import logging

import numpy as np
import threading
import pandas as pd

from scipy.integrate import simpson
from scipy.signal import find_peaks, peak_widths

from piccolo.controllers.controller import InstrumentController

logger = logging.getLogger(__name__)


class HardwareSimulator(InstrumentController):
    def __init__(self,
                 num_channels=4,
                 signal_length=4096,
                 sampling_interval_ms=0.02,
                 drop_interval_ms=1,
                 drop_width_ms=0.2,
                 drop_signal_cv=0.2,
                 signal_baseline=0.01,
                 signal_baseline_cv=0.01,
                 min_width=0.1,
                 max_width=1,
                 name='Data_generator',
                 verbose=True,
                 very_verbose=False,
                 ):
        # Convert args to attributes
        args = locals()
        args.pop('self')
        for k, v in args.items():
            if v is not None:
                setattr(self, k, v)

        logger.debug("%s: opening...", self.name)

        self.time_ms = np.arange(0, signal_length) * sampling_interval_ms
        self.signal = [np.zeros_like(self.time_ms)] * num_channels
        self.drop_arrival_time_ms = np.arange(0, signal_length) * drop_interval_ms

        # ADC data attributes
        self.adc1_data = []
        self.adc2_data = []
        self.adc3_data = []
        self.adc4_data = []

        # Laser box (None = laser control disabled)
        self.laser_box = None

        # Calibration values
        self.calibration_values = {
            "CH1": [-10, 1.0],
            "CH2": [-10, 1.0],
            "CH3": [-10, 1.0],
            "CH4": [-10, 1.0],
        }

        # FPGA register cache — must be before set_detection_threshold
        self.fpga_registers = {
            "fads_reset": 0,
            "sort_delay": 100,
            "sort_duration": 50,
            "sort_enable": 0,
            "detection_enable": 0,
            "enabled_channels": 15,
            "detection_channel": 0,
            "camera_trig_delay": 0,
            "camera_trig_duration": 50,
            "droplet_counter": 0,
            "sorted_droplet_counter": 0,
            "droplet_frequency": 0,
        }
        for i in range(4):
            self.fpga_registers[f"min_intensity_thresh[{i}]"] = 30
            self.fpga_registers[f"low_intensity_thresh[{i}]"] = 0
            self.fpga_registers[f"high_intensity_thresh[{i}]"] = 6106
            self.fpga_registers[f"min_width_thresh[{i}]"] = 6000
            self.fpga_registers[f"low_width_thresh[{i}]"] = 6000
            self.fpga_registers[f"high_width_thresh[{i}]"] = 125000
            self.fpga_registers[f"min_area_thresh[{i}]"] = 0
            self.fpga_registers[f"low_area_thresh[{i}]"] = 1000000
            self.fpga_registers[f"high_area_thresh[{i}]"] = 3437096703

        # Detection and sorting state
        self.sort_gates = {}
        self.sipm_gain = np.zeros(num_channels)
        for ch in range(num_channels):
            self.set_sipm_gain(ch, 0.5)
        self.set_detection_threshold(0.03)

        # Droplet data buffer
        self.droplet_data = pd.DataFrame()
        self.buffer_size = 1000

        # Generation thread state
        self._running = False

        logger.debug("%s: open and ready.", self.name)

    ################ Abstract Method Implementations ################

    def set_memory_variable(self, name, value):
        """Set a simulated FPGA register value."""
        logger.debug("Setting memory variable %s to %s", name, value)
        self.fpga_registers[name] = value

    def set_laser_on_state(self, name, state):
        """Stub — no laser hardware in simulation."""
        logger.debug("Laser '%s' on state -> %s (simulated, no-op)", name, state)

    def set_laser_power(self, name, power_mw):
        """Stub — no laser hardware in simulation."""
        logger.debug("Laser '%s' power -> %s mW (simulated, no-op)", name, power_mw)

    def start(self):
        """Start signal generation."""
        self.start_generating()

    def stop(self):
        """Stop signal generation."""
        self.stop_generating()

    ################ Signal Generation ################

    def start_generating(self):
        logger.debug("%s: start generating", self.name)
        self._running = True
        self._thread = threading.Thread(target=self._continue_generating, daemon=True)
        self._thread.start()

    def stop_generating(self):
        logger.debug("%s: stop generating", self.name)
        if self._running:
            self._running = False
            self._thread.join()

    def _continue_generating(self):
        logger.debug("%s: continue generating", self.name)
        while self._running:
            self._generate_signal()
            self._analyze_drops()

    def _generate_signal(self):
        logger.debug("%s: generate signal", self.name)
        for ch in range(self.num_channels):
            signal = np.zeros_like(self.time_ms)
            for t in self.drop_arrival_time_ms:
                drop_signal = np.exp(
                    -((self.time_ms - t) / (
                        2 * self.drop_width_ms / 2.355)) ** 2)
                drop_signal *= np.random.normal(1, self.drop_signal_cv)
                signal += drop_signal
            baseline_noise = np.random.normal(loc=self.signal_baseline,
                                              scale=self.signal_baseline_cv,
                                              size=len(self.time_ms))
            self.signal[ch] = (signal + baseline_noise) * self.sipm_gain[ch]

        self.adc1_data = self.signal[0]
        self.adc2_data = self.signal[1]
        self.adc3_data = self.signal[2]
        self.adc4_data = self.signal[3]

        logger.debug("%s: done generating signal", self.name)

    def _analyze_drops(self):
        logger.debug("%s: analyzing drops", self.name)

        detection_ch = self.fpga_registers.get('detection_channel', 0)
        drops, _ = find_peaks(self.signal[detection_ch], height=self.threshold)
        if np.any(drops) == False:
            logger.debug("No peaks detected in reference channel")
        else:
            widths, _, left_ips, right_ips = peak_widths(self.signal[detection_ch], drops, rel_height=0.5)
            drop_widths = widths * self.sampling_interval_ms
            valid_drop_indices = np.where(
                (drop_widths >= self.min_width) &
                (drop_widths <= self.max_width))[0]
            valid_left_ips = left_ips[valid_drop_indices]
            valid_right_ips = right_ips[valid_drop_indices]
            valid_drop_widths = drop_widths[valid_drop_indices]
            excluded_indices = np.array([], dtype=int)
            for left, right in zip(left_ips, right_ips):
                excluded_indices = np.concatenate(
                    (excluded_indices, np.arange(int(left), int(right))))
            if np.any(valid_drop_indices) == False:
                logger.debug("Drops failed validity tests")
            else:
                results = {"channel": [], "id": [], "timestamp": [],
                           "width": [], "max signal": [], "auc": [],
                           "fwhm": [], "baseline": []}
                baseline_signals = {}
                for i, (left, right, width) in enumerate(
                        zip(valid_left_ips, valid_right_ips, valid_drop_widths),
                        start=1):
                    for ch in range(self.num_channels):
                        baseline_indices = np.setdiff1d(
                            np.arange(len(self.signal[ch])), excluded_indices)
                        baseline_signals[ch] = np.median(
                            self.signal[ch][baseline_indices])
                        baseline = np.mean(baseline_signals[ch])
                        drop_signal = self.signal[ch][int(left):int(right)]
                        max_signal = drop_signal.max()
                        drop_time = self.time_ms[int(left)]
                        auc = simpson(drop_signal, dx=self.sampling_interval_ms)
                        fwhm = width
                        drop_width = (right - left) * self.sampling_interval_ms
                        results["channel"].append(ch)
                        results["id"].append(i)
                        results["timestamp"].append(drop_time)
                        results["width"].append(drop_width)
                        results["max signal"].append(max_signal)
                        results["auc"].append(auc)
                        results["fwhm"].append(fwhm)
                        results["baseline"].append(baseline)

                df = pd.DataFrame(results)
                pivot_df = df.pivot(index='id', columns='channel')

                final_df = pd.DataFrame()
                for ch in range(self.num_channels):
                    final_df[f'cur_droplet_intensity[{ch}]'] = pivot_df['max signal'][ch]
                    final_df[f'cur_droplet_intensity_v[{ch}]'] = pivot_df['max signal'][ch]
                    final_df[f'cur_droplet_width[{ch}]'] = pivot_df['width'][ch]
                    final_df[f'cur_droplet_width_ms[{ch}]'] = pivot_df['width'][ch]
                    final_df[f'cur_droplet_area[{ch}]'] = pivot_df['auc'][ch]
                    final_df[f'cur_droplet_area_vms[{ch}]'] = pivot_df['auc'][ch]

                self._on_memory_data(final_df)
                self.fpga_registers['droplet_counter'] += len(final_df)

        logger.debug("%s: done analysing drops", self.name)

    def _on_memory_data(self, fpgaoutput):
        self.droplet_data = pd.concat([self.droplet_data, fpgaoutput], ignore_index=True)
        if len(self.droplet_data) > self.buffer_size:
            self.droplet_data = self.droplet_data.iloc[-self.buffer_size:]

    ################ Sim-specific ################

    def set_detection_threshold(self, thresh, ch=0):
        """Override to also store threshold for peak detection."""
        self.threshold = thresh
        super().set_detection_threshold(thresh, ch)

    def set_sipm_gain(self, ch, gain):
        logger.debug("%s(ch%s): setting sipm gain = %s", self.name, ch, gain)
        self.sipm_gain[ch] = gain
