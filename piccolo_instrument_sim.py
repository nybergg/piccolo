# Imports from the python standard library:
import numpy as np
import threading

# Third party imports, installable via pip:
from scipy.integrate import simpson
from scipy.signal import find_peaks, peak_widths
from scipy.stats import gaussian_kde

class InstrumentSim:
    def __init__(self,
                 num_channels=2,
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
        self.set_threshold(0.03)
        self.set_gate_limits(sort_keys=["cur_droplet_intensity[0]", "cur_droplet_intensity[1]"], 
                             limits={"x0": 0, "y0": 0, "x1": 0, "y1": 0})
        self.sipm_gain = np.zeros(num_channels)
        for ch in range(num_channels):
            self.set_sipm_gain(ch, 0.5)
        self.data2d = {"x": [0], "y": [0], "density": [0]}
        self._running = False
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
                        results["auc"].append(auc * 1e6)
                        results["fwhm"].append(fwhm)
                        results["baseline"].append(baseline)
                # Calculate density measurement for the density scatter plot:
                auc_1 = [
                    results["auc"][i]
                    for i, channel_value in enumerate(results["channel"])
                    if channel_value == 0
                    ]
                auc_2 = [
                    results["auc"][i]
                    for i, channel_value in enumerate(results["channel"])
                    if channel_value == 1
                    ]
                # Locate auc values that are zero and give them a negligible
                # non-zero value
                auc_1 = [x if x > 0 else 0.001 for x in auc_1]
                auc_2 = [x if x > 0 else 0.001 for x in auc_2]
                if np.size(auc_1) > 2:
                    xy = np.vstack([np.log(auc_1), np.log(auc_2)])
                    density = gaussian_kde(xy)(xy)
                    self.droplet_data = {"x": auc_1, "y": auc_2, "density": density}
        if self.very_verbose:
            print("\n%s: -> done analysing drops"%self.name)
        return None

    def set_threshold(self, threshold):
        if self.verbose:
            print("%s: setting threshold = %s"%(self.name, threshold))
        self.threshold = threshold
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

if __name__ == "__main__":
    import time
    dg = InstrumentSim(verbose=True, very_verbose=True)
    dg.start_generating()
    time.sleep(0.5) # run for a bit
    input('\nhit enter to continue')
    dg.stop_generating()