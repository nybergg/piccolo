# Imports from the python standard library:
import numpy as np
import threading
import pandas as pd

# Third party imports, installable via pip:
from scipy.integrate import simpson
from scipy.signal import find_peaks, peak_widths
from scipy.stats import gaussian_kde

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
        self.set_detection_threshold(0.03)
        self.set_gate_limits(sort_keys=["cur_droplet_intensity[0]", "cur_droplet_intensity[1]"], 
                             limits={"x0": 0, "y0": 0, "x1": 0, "y1": 0})
        self.sipm_gain = np.zeros(num_channels)
        for ch in range(num_channels):
            self.set_sipm_gain(ch, 0.5)
        self.droplet_data = pd.DataFrame()
        self.buffer_length = 1000
        self._running = False
        self.sorter_on = True
        self.fpga_registers = {
            'droplet_counter': 0,
            'sorted_droplet_counter': 0,
            'droplet_frequency': 0,
        }
        if self.verbose:
            print("%s: -> open and ready."%self.name)

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
        if self.very_verbose:
            print("\n%s: -> done generating signal"%self.name)            
        return None

    def _analyze_drops(self, ch=1):
        if self.very_verbose:
            print("\n%s: analyzing drops"%self.name)
        # Analyze Drop Parameters from sipm Signals:
        # Find drops based on the signal and threshold of the specified channel:
        drops, _ = find_peaks(self.signal[ch], height=self.threshold)
        if np.any(drops) == False:
            print('No peaks detected in reference channel')
        else:
            # Calculate fwhm of peaks to define time range for each drop:
            widths, _, left_ips, right_ips = peak_widths(
                self.signal[ch], drops, rel_height=0.5)
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
                        # (technically don't need to do this for every drop)
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

                # Create new column names
                new_cols = [f'cur_droplet_intensity[{col[1]}]', f'cur_droplet_intensity_v[{col[1]}]', 
                            f'cur_droplet_width[{col[1]}]', f'cur_droplet_width_ms[{col[1]}]',
                            f'cur_droplet_area[{col[1]}]', f'cur_droplet_area_vms[{col[1]}]']
                
                final_df = pd.DataFrame()
                for ch in range(self.num_channels):
                    final_df[f'cur_droplet_intensity[{ch}]'] = pivot_df['max signal'][ch]
                    final_df[f'cur_droplet_intensity_v[{ch}]'] = pivot_df['max signal'][ch]
                    final_df[f'cur_droplet_width[{ch}]'] = pivot_df['width'][ch]
                    final_df[f'cur_droplet_width_ms[{ch}]'] = pivot_df['width'][ch]
                    final_df[f'cur_droplet_area[{ch}]'] = pivot_df['auc'][ch]
                    final_df[f'cur_droplet_area_vms[{ch}]'] = pivot_df['auc'][ch]

                self._on_memory_data(final_df)

        if self.very_verbose:
            print("\n%s: -> done analysing drops"%self.name)
        return None
    
    def _on_memory_data(self, fpgaoutput):
        # Append to DataFrame
        self.droplet_data = pd.concat([self.droplet_data, fpgaoutput], ignore_index=True)

        # Maintain rolling size
        if len(self.droplet_data) > self.buffer_length:
            self.droplet_data = self.droplet_data.iloc[-self.buffer_length:]

        return self.droplet_data

    def set_detection_threshold(self, thresh, thresh_key=None):
        if self.verbose:
            print("%s: setting threshold = %s"%(self.name, thresh))
        self.threshold = thresh
        return None

    def set_gate_limits(self, sort_keys, limits):
        if self.verbose:
            print("%s: setting gate limits for %s"%(self.name, sort_keys))
            print("%s: setting gate limits = %s"%(self.name, limits))        
        self.gate_limits = limits
        return None

    def set_sipm_gain(self, ch, gain):
        if self.verbose:
            print("%s(ch%s): setting sipm gain = %s"%(self.name, ch, gain))
        self.sipm_gain[ch] = gain
        return None

    def enable_sorter(self, state):
        if self.verbose:
            print(f"%s: setting sorter to {state}"%self.name)
        self.sorter_on = state
        return None

    def save_droplet_data_log(self, filename):
        if self.verbose:
            print(f"%s: saving droplet data to {filename}"%self.name)
        self.droplet_data.to_csv(filename, index=False)
        return None

    def save_adc_log(self, filename):
        if self.verbose:
            print(f"%s: saving adc data to {filename}"%self.name)
        df = pd.DataFrame(np.transpose(self.signal))
        df.to_csv(filename, index=False)
        return None

    def set_memory_variable(self, name, value):
        if self.verbose:
            print(f"%s: setting memory variable {name} to {value}"%self.name)
        if name in self.fpga_registers:
            self.fpga_registers[name] = value
        return None

    def get_fpga_registers(self):
        return self.fpga_registers

    def get_fpga_registers_converted(self):
        return self.fpga_registers

    def convert_volts_to_raw(self, volts, ch):
        return int(volts * 1000) # Dummy conversion

    def start_generating(self):
        if self.verbose:
            print("\n%s: start generating"%self.name)
        self._running = True
        self._thread = threading.Thread(target=self._continue_generating)
        self._thread.start()
        return None

    def stop_generating(self):
        if self.verbose:
            print("\n%s: stop generating"%self.name)
        if self._running:
            self._running = False
            self._thread.join()
        return None

    def stop(self):
        self.stop_generating()

if __name__ == "__main__":
    import time
    dg = InstrumentSim(verbose=True, very_verbose=True)
    dg.start_generating()
    time.sleep(0.5) # run for a bit
    input('\nhit enter to continue')
    dg.stop()
