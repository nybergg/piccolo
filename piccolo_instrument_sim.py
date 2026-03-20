# Imports from the python standard library:
import re
import numpy as np
import threading
import pandas as pd

# Third party imports, installable via pip:
from scipy.integrate import simpson
from scipy.signal import find_peaks, peak_widths


class InstrumentSim:
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
        # convert args to attributes:
        args = locals()
        args.pop('self')
        for k, v in args.items():
            if v is not None:
                setattr(self, k, v) # A lot like self.x = x
        # init:
        if self.verbose:
            print("%s: opening..."%self.name)
        self.time_ms = np.arange(0, signal_length) * sampling_interval_ms
        self.signal = [np.zeros_like(self.time_ms)] * num_channels
        self.drop_arrival_time_ms = np.arange(0, signal_length) * drop_interval_ms

        # ADC data attributes (matching Instrument interface)
        self.adc1_data = []
        self.adc2_data = []
        self.adc3_data = []
        self.adc4_data = []

        # Laser box (None = laser control disabled, matching Instrument)
        self.laser_box = None

        # Calibration values (matching Instrument)
        self.calibration_values = {
            "CH1": [-10, 1.0],
            "CH2": [-10, 1.0],
            "CH3": [-10, 1.0],
            "CH4": [-10, 1.0],
        }

        # FPGA register cache (matching Instrument layout) — must be before set_detection_threshold
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

        if self.verbose:
            print("%s: -> open and ready."%self.name)


    ################ Signal Generation ################

    def _continue_generating(self):
        if self.very_verbose:
            print("\n%s: continue generating"%self.name)
        while True:
            if self._running:
                self._generate_signal()
                self._analyze_drops()
            else:
                break
        return None

    def _generate_signal(self):
        if self.very_verbose:
            print("\n%s: generate signal"%self.name)
        for ch in range(self.num_channels):
            signal = np.zeros_like(self.time_ms)
            # Generate drop signals:
            for t in self.drop_arrival_time_ms:
                drop_signal = np.exp(
                    -((self.time_ms - t) / (
                    2 * self.drop_width_ms / 2.355)) ** 2)
                drop_signal *= np.random.normal(1, self.drop_signal_cv)
                signal += drop_signal
            # Generate baseline noise:
            baseline_noise = np.random.normal(loc=self.signal_baseline,
                                              scale=self.signal_baseline_cv,
                                              size=len(self.time_ms))
            # Combine signals for this channel:
            self.signal[ch] = (signal + baseline_noise) * self.sipm_gain[ch]

        # Update ADC data attributes to match Instrument interface
        self.adc1_data = self.signal[0]
        self.adc2_data = self.signal[1]
        self.adc3_data = self.signal[2]
        self.adc4_data = self.signal[3]

        if self.very_verbose:
            print("\n%s: -> done generating signal"%self.name)
        return None

    def _analyze_drops(self):
        if self.very_verbose:
            print("\n%s: analyzing drops"%self.name)

        detection_ch = self.fpga_registers.get('detection_channel', 0)
        # Analyze Drop Parameters from sipm Signals:
        # Find drops based on the signal and threshold of the specified channel:
        drops, _ = find_peaks(self.signal[detection_ch], height=self.threshold)
        if np.any(drops) == False:
            print('No peaks detected in reference channel')
        else:
            # Calculate fwhm of peaks to define time range for each drop:
            widths, _, left_ips, right_ips = peak_widths(self.signal[detection_ch], drops, rel_height=0.5)
            # Convert widths to time units:
            drop_widths = widths * self.sampling_interval_ms
            # Filter drops based on width constraints:
            valid_drop_indices = np.where(
                (drop_widths >= self.min_width) &
                (drop_widths <= self.max_width))[0]
            valid_left_ips = left_ips[valid_drop_indices]
            valid_right_ips = right_ips[valid_drop_indices]
            valid_drop_widths = drop_widths[valid_drop_indices]
            # Prepare to exclude signal within drop time ranges from baseline
            # calculation:
            excluded_indices = np.array([], dtype=int)
            for left, right in zip(left_ips, right_ips):
                excluded_indices = np.concatenate(
                    (excluded_indices, np.arange(int(left), int(right))))
            if np.any(valid_drop_indices) == False:
                print('Drops failed validity tests')
            else:
                # Initialize a dictionary to store the results:
                results = {"channel": [],
                           "id": [],
                           "timestamp": [],
                           "width": [],
                           "max signal": [],
                           "auc": [],
                           "fwhm": [],
                           "baseline": [],
                           }
                # Initialize dictionary for baseline signals:
                baseline_signals = {}
                # For each valid drop, calculate parameters:
                for i, (left, right, width) in enumerate(
                    zip(valid_left_ips, valid_right_ips, valid_drop_widths),
                    start=1):
                    for ch in range(self.num_channels):
                        # Isolate baseline signal by excluding drop indices:
                        baseline_indices = np.setdiff1d(
                            np.arange(len(self.signal[ch])), excluded_indices)
                        baseline_signals[ch] = np.median(
                            self.signal[ch][baseline_indices])
                        baseline = np.mean(baseline_signals[ch])
                        # Isolate drop signal:
                        drop_signal = self.signal[ch][int(left) : int(right)]
                        # Calculate drop parameters:
                        max_signal = drop_signal.max()
                        drop_time = self.time_ms[int(left)]
                        auc = simpson(drop_signal, dx=self.sampling_interval_ms)
                        fwhm = width
                        drop_width = (right - left) * self.sampling_interval_ms
                        # Append drop parameter dictionary:
                        results["channel"].append(ch)
                        results["id"].append(i)
                        results["timestamp"].append(drop_time)
                        results["width"].append(drop_width)
                        results["max signal"].append(max_signal)
                        results["auc"].append(auc)
                        results["fwhm"].append(fwhm)
                        results["baseline"].append(baseline)

                # Create a DataFrame from the results
                df = pd.DataFrame(results)

                # Pivot the DataFrame to get one row per drop ID
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

                # Update simulated counters
                self.fpga_registers['droplet_counter'] += len(final_df)

        if self.very_verbose:
            print("\n%s: -> done analysing drops"%self.name)
        return None

    def _on_memory_data(self, fpgaoutput):
        # Append to DataFrame
        self.droplet_data = pd.concat([self.droplet_data, fpgaoutput], ignore_index=True)

        # Maintain rolling size
        if len(self.droplet_data) > self.buffer_size:
            self.droplet_data = self.droplet_data.iloc[-self.buffer_size:]

        return self.droplet_data


    ################ Detection and Sorting ################

    def enable_detection(self, enable: bool):
        """Enable or disable droplet detection."""
        value_to_set = 1 if enable else 0
        self.set_memory_variable("detection_enable", value_to_set)
        if self.verbose:
            status = "enabled" if enable else "disabled"
            print(f"[InstrumentSim] Droplet detection has been {status}.")

    def enable_sorter(self, enable: bool):
        """Enable or disable the droplet sorter."""
        value_to_set = 1 if enable else 0
        self.set_memory_variable("sort_enable", value_to_set)
        if self.verbose:
            status = "enabled" if enable else "disabled"
            print(f"[InstrumentSim] Sorter has been {status}.")

    def set_detection_threshold(self, thresh, ch=0):
        if self.verbose:
            print("%s: setting threshold = %s"%(self.name, thresh))
            print("%s: setting detection channel = %s"%(self.name, ch))
        self.threshold = thresh
        thresh_key = f"min_intensity_thresh[{ch}]"
        thresh_raw = self.convert_volts_to_raw(thresh, ch)
        self.set_memory_variable("detection_channel", ch)
        self.set_memory_variable(thresh_key, int(thresh_raw))

    def set_gate_limits(self, sort_keys, limits):
        """Set sort gate limits, matching Instrument interface."""
        if self.verbose:
            print(f"[InstrumentSim] Received gate limits to set: {limits}")

        for i, key in enumerate(sort_keys):
            # Parse channel index
            ch = int(key[key.find('[')+1:key.find(']')])

            # Select x/y based on index
            low_coord = 'x0' if i == 0 else 'y0'
            high_coord = 'x1' if i == 0 else 'y1'

            # Handle both dict-of-lists (from UI) and plain dict (from init)
            low_val = limits[low_coord]
            high_val = limits[high_coord]
            if isinstance(low_val, list):
                low_val = low_val[0]
            if isinstance(high_val, list):
                high_val = high_val[0]

            # Determine parameter type
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

        if self.verbose:
            print(f"[InstrumentSim] Setting cumulative sort gates: {self.sort_gates}")

        # Update FPGA register cache
        for var, val in self.sort_gates.items():
            self.set_memory_variable(var, int(val))

        return self.sort_gates

    def get_sort_gates(self):
        """Returns the currently configured sort gates."""
        return self.sort_gates


    ################ Laser Control (stubs) ################

    def set_laser_on_state(self, name, state):
        """Stub — no laser hardware in simulation."""
        if self.verbose:
            print(f"[InstrumentSim] Laser '{name}' on state -> {state} (simulated, no-op)")

    def set_laser_power(self, name, power_mw):
        """Stub — no laser hardware in simulation."""
        if self.verbose:
            print(f"[InstrumentSim] Laser '{name}' power -> {power_mw} mW (simulated, no-op)")


    ################ FPGA Register Access ################

    def set_memory_variable(self, name, value):
        if self.verbose:
            print(f"[InstrumentSim] Setting memory variable {name} to {value}")
        self.fpga_registers[name] = value

    def get_fpga_registers(self):
        """Return the cached dictionary of FPGA register values."""
        return self.fpga_registers

    def get_fpga_registers_converted(self):
        """
        Return a dictionary of FPGA registers with human-readable values and units.
        Each value is a tuple: (converted_value, unit_string).
        Matches the Instrument.get_fpga_registers_converted() interface.
        """
        display_registers = {}
        raw_registers = self.get_fpga_registers()

        for name, value in raw_registers.items():
            display_value = value
            unit = ""

            ch_match = re.search(r'\[(\d)\]', name)
            ch = int(ch_match.group(1)) if ch_match else None

            try:
                numeric_value = int(value)

                if ch is not None:
                    if 'intensity_thresh' in name:
                        display_value = self.convert_raw_to_volts(numeric_value, ch)
                        unit = "V"
                    elif 'area_thresh' in name:
                        display_value = self.convert_raw_to_volts(numeric_value, ch) / 1000.0
                        unit = "V·ms"
                    elif 'width_thresh' in name:
                        display_value = numeric_value / 1000.0
                        unit = "ms"
                elif 'sort_delay' in name or 'sort_duration' in name or 'camera_trig_delay' in name or 'camera_trig_duration' in name:
                    display_value = numeric_value / 1000.0
                    unit = "ms"
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


    ################ Unit Conversion ################

    def convert_raw_to_volts(self, raw_value, ch):
        """Convert raw ADC value to volts using calibration values."""
        vp = 20.0
        adc_max = 8192.0
        ch_key = f"CH{ch+1}"
        offset, gain = self.calibration_values[ch_key]
        volt_value = (raw_value - offset) * gain / adc_max * vp
        return volt_value

    def convert_volts_to_raw(self, volt_value, ch):
        """Convert volts to raw ADC value using calibration values."""
        vp = 20.0
        adc_max = 8192.0
        ch_key = f"CH{ch+1}"
        offset, gain = self.calibration_values[ch_key]
        raw_value = (volt_value * adc_max / vp) / gain + offset
        return int(raw_value)


    ################ Data Logging ################

    def save_droplet_data_log(self, filename="droplet_log.csv"):
        if self.verbose:
            print(f"[InstrumentSim] Saving droplet data to {filename}")
        self.droplet_data.to_csv(filename, index=False)

    def clear_droplet_data(self):
        """Clears the internal droplet data buffer."""
        if self.verbose:
            print("[InstrumentSim] Clearing droplet data buffer.")
        self.droplet_data = pd.DataFrame()

    def save_adc_log(self, filename="adc_log.csv"):
        """Save ADC data to CSV, matching Instrument format."""
        if self.verbose:
            print(f"[InstrumentSim] Saving ADC data to {filename}")
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

    def set_sipm_gain(self, ch, gain):
        if self.verbose:
            print("%s(ch%s): setting sipm gain = %s"%(self.name, ch, gain))
        self.sipm_gain[ch] = gain


    ################ Start / Stop ################

    def start_generating(self):
        if self.verbose:
            print("\n%s: start generating"%self.name)
        self._running = True
        self._thread = threading.Thread(target=self._continue_generating, daemon=True)
        self._thread.start()

    def stop_generating(self):
        if self.verbose:
            print("\n%s: stop generating"%self.name)
        if self._running:
            self._running = False
            self._thread.join()

    def stop(self):
        self.stop_generating()


if __name__ == "__main__":
    import time
    dg = InstrumentSim(verbose=True, very_verbose=True)
    dg.start_generating()
    time.sleep(0.5) # run for a bit
    input('\nhit enter to continue')
    dg.stop()