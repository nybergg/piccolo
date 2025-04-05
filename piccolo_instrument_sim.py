# Imports from the python standard library:
import numpy as np
import threading

# Third party imports, installable via pip:
from scipy.integrate import simpson
from scipy.signal import find_peaks, peak_widths
from scipy.stats import gaussian_kde

class DataGenerator:
    def __init__(self,
                 num_channels=2,
                 sampling_interval=0.02,    # time units in ms
                 signal_duration=100,
                 baseline=0.01,
                 drop_interval=1,
                 drop_width=0.2,
                 drop_cv=0.2,
                 baseline_cv=0.01,
                 min_width=0.1,
                 max_width=1
                 ):
        # convert args to attributes:
        args = locals()
        args.pop('self')
        for k, v in args.items(): 
            if v is not None:
                setattr(self, k, v) # A lot like self.x = x
        self.data = {"pmt1": {"x": [0], "y": [0]}, "pmt2": {"x": [0], "y": [0]}}
        self.data2d = {"x": [0], "y": [0], "density": [0]}
        self._generate = False
        self.gain = [0.5, 0.5]
        self.thresh = 0.03
        self.gate_val = {"x0": [0], "y0": [0], "x1": [0], "y1": [0]}

    def _continue_generating(self):
        while True:
            if not self._generate:
                return
            self._generate_signal()
            self._analyze_drops()
        return None

    def _generate_signal(self):
        # Generate Test PMT Signals:
        t = np.arange(0, self.signal_duration, self.sampling_interval)

        for channel_idx in range(1, self.num_channels + 1):
            # Generate baseline noise
            baseline_noise = np.random.normal(
                loc=self.baseline, scale=self.baseline_cv, size=len(t)
            )

            # Generate drops
            drops = np.zeros_like(t)
            for start in np.arange(0, self.signal_duration, self.drop_interval):
                drop = np.exp(
                    -((t - start) ** 2) / (2 * (self.drop_width / 2.355) ** 2))
                drop *= np.random.normal(1, self.drop_cv)
                drops += drop

            # Combine signals for this channel
            signal = baseline_noise + drops
            signal = signal * self.gain[channel_idx - 1]
            self.data[f"pmt{channel_idx}"] = {"x": t, "y": signal}
        return None

    def _analyze_drops(self, detection_channel=1):
        # Analyze Drop Parameters from PMT Signals:
        # Find drops based on the signal and threshold of the specified channel
        detection_signal = self.data[f"pmt{detection_channel}"]["y"]
        drops, _ = find_peaks(detection_signal, height=self.thresh)

        if np.any(drops) == False:
            print('No peaks detected in reference channel')

        else:
            # Calculate widths (fwhm) of the peaks to define the time range for each drop
            widths, _, left_ips, right_ips = peak_widths(
                detection_signal, drops, rel_height=0.5
            )
            drop_widths = widths * self.sampling_interval  # Convert widths to time units

            # Filter drops based on width constraints
            valid_drop_indices = np.where(
                (drop_widths >= self.min_width) & (drop_widths <= self.max_width)
            )[0]
            valid_left_ips = left_ips[valid_drop_indices]
            valid_right_ips = right_ips[valid_drop_indices]
            valid_drop_widths = drop_widths[valid_drop_indices]

            # Prepare to exclude signal within drop time ranges from baseline calculation
            excluded_indices = np.array([], dtype=int)
            for left, right in zip(left_ips, right_ips):
                excluded_indices = np.concatenate(
                    (excluded_indices, np.arange(int(left), int(right)))
                )

            if np.any(valid_drop_indices) == False:
                print('Drops failed validity tests')
            
            else:
                # Initialize a dictionary to store the results
                results = {
                    "channel": [],
                    "id": [],
                    "timestamp": [],
                    "width": [],
                    "max signal": [],
                    "auc": [],
                    "fwhm": [],
                    "baseline": [],
                }

                # Initialize dictionary for baseline signals
                baseline_signals = {}

                # For each valid drop, calculate parameters
                for i, (left, right, width) in enumerate(
                    zip(valid_left_ips, valid_right_ips, valid_drop_widths), start=1
                ):
                    for channel in range(1, self.num_channels + 1):
                        # Specify the signal from a given channel
                        channel_signal = self.data[f"pmt{channel}"]["y"]

                        # Isolate baseline signal by excluding drop indices - technically don't need to calculate this for every drop
                        baseline_indices = np.setdiff1d(
                            np.arange(len(channel_signal)), excluded_indices
                        )
                        baseline_signals[channel] = np.median(
                            channel_signal[baseline_indices]
                        )
                        baseline = np.mean(baseline_signals[channel])

                        # Isolate drop signal
                        drop_signal = channel_signal[int(left) : int(right)]

                        # Calculate drop parameters
                        max_signal = drop_signal.max()
                        drop_time = self.data[f"pmt{channel}"]["x"][int(left)]
                        auc = simpson(drop_signal, dx=self.sampling_interval)
                        fwhm = width
                        drop_width = (right - left) * self.sampling_interval

                        # Append drop parameter dictionary
                        results["channel"].append(channel)
                        results["id"].append(i)
                        results["timestamp"].append(drop_time)
                        results["width"].append(drop_width)
                        results["max signal"].append(max_signal)
                        results["auc"].append(auc * 1e6)
                        results["fwhm"].append(fwhm)
                        results["baseline"].append(baseline)

                # Calculate density measurement for the density scatter plot
                auc_1 = [
                    results["auc"][i]
                    for i, channel_value in enumerate(results["channel"])
                    if channel_value == 1
                ]
                auc_2 = [
                    results["auc"][i]
                    for i, channel_value in enumerate(results["channel"])
                    if channel_value == 2
                ]

                # Locate auc values that are zero and give them a negligible, non-zero value
                auc_1 = [x if x > 0 else 0.001 for x in auc_1]
                auc_2 = [x if x > 0 else 0.001 for x in auc_2]

                if np.size(auc_1) > 2:
                    xy = np.vstack([np.log(auc_1), np.log(auc_2)])
                    density = gaussian_kde(xy)(xy)
                    self.data2d = {"x": auc_1, "y": auc_2, "density": density}
        return None

    def start_generating(self):
        self._generate = True
        self._thread = threading.Thread(target=self._continue_generating)
        self._thread.start()
        return None

    def stop_generating(self):
        self._generate = False
        if hasattr(self, "_thread"):
            self._thread.join()
        return None

    def set_gain(self, value, channel=1):
        self.gain[channel - 1] = value
        return None

    def set_thresh(self, value):
        self.thresh = value
        return None

    def set_gate_values(self, values):
        self.gate_val = values
        print(f"Gate values set {self.gate_val}")
        return None

if __name__ == "__main__":
    dg = DataGenerator()
    dg.start_generating()
    input()
    dg.stop_generating()
