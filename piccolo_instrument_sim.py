# Imports from the python standard library:
import numpy as np
import threading

# Third party imports, installable via pip:
from scipy.integrate import simpson
from scipy.signal import find_peaks, peak_widths
from scipy.stats import gaussian_kde

class DataGenerator:
    NUM_CHANNELS = 2
    SAMPLING_INTERVAL = 0.02  # time units in ms
    SIGNAL_DURATION = 100
    BASELINE = 0.01
    DROP_INTERVAL = 1
    DROP_WIDTH = 0.2
    DROP_CV = 0.2
    BASELINE_CV = 0.01
    MIN_WIDTH = 0.1
    MAX_WIDTH = 1

    """ Initialization """

    def __init__(self):
        self.data = {"pmt1": {"x": [0], "y": [0]}, "pmt2": {"x": [0], "y": [0]}}
        self.data2d = {"x": [0], "y": [0], "density": [0]}
        self._generate = False
        self.gain = [0.5, 0.5]
        self.thresh = 0.03
        self.gate_val = {"x0": [0], "y0": [0], "x1": [0], "y1": [0]}

    """ Start, Stop, Continue Methods to Run in the Background """

    def start_generating(self):
        self._generate = True
        self._thread = threading.Thread(target=self._continue_generating)
        self._thread.start()

    def stop_generating(self):
        self._generate = False
        if hasattr(self, "_thread"):
            self._thread.join()

    def _continue_generating(self):
        while True:
            if not self._generate:
                return
            self._generate_signal()
            self._analyze_drops()

    """ Generate Test PMT Signals """

    def _generate_signal(
        self,
        num_channels=NUM_CHANNELS,
        sampling_interval=SAMPLING_INTERVAL,
        signal_duration=SIGNAL_DURATION,
        baseline=BASELINE,
        drop_interval=DROP_INTERVAL,
        drop_width=DROP_WIDTH,
        drop_cv=DROP_CV,
        baseline_cv=BASELINE_CV,
    ):
        t = np.arange(0, signal_duration, sampling_interval)

        for channel_idx in range(1, num_channels + 1):
            # Generate baseline noise
            baseline_noise = np.random.normal(
                loc=baseline, scale=baseline_cv, size=len(t)
            )

            # Generate drops
            drops = np.zeros_like(t)
            for start in np.arange(0, signal_duration, drop_interval):
                drop = np.exp(-((t - start) ** 2) / (2 * (drop_width / 2.355) ** 2))
                drop *= np.random.normal(1, drop_cv)
                drops += drop

            # Combine signals for this channel
            signal = baseline_noise + drops
            signal = signal * self.gain[channel_idx - 1]
            self.data[f"pmt{channel_idx}"] = {"x": t, "y": signal}

    """ Analyze Drop Parameters from PMT Signals """

    def _analyze_drops(
        self,
        num_channels=NUM_CHANNELS,
        detection_channel=1,
        sampling_interval=SAMPLING_INTERVAL,
        min_width=MIN_WIDTH,
        max_width=MAX_WIDTH,
    ):
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
            drop_widths = widths * sampling_interval  # Convert widths to time units

            # Filter drops based on width constraints
            valid_drop_indices = np.where(
                (drop_widths >= min_width) & (drop_widths <= max_width)
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
                    for channel in range(1, num_channels + 1):
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
                        auc = simpson(drop_signal, dx=sampling_interval)
                        fwhm = width
                        drop_width = (right - left) * sampling_interval

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

    """ Set hardware values based on UI callbacks """

    def set_gain(self, value, channel=1):
        self.gain[channel - 1] = value

    def set_thresh(self, value):
        self.thresh = value

    def set_gate_values(self, values):
        self.gate_val = values
        print(f"Gate values set {self.gate_val}")


if __name__ == "__main__":
    dg = DataGenerator()
    dg.start_generating()
    input()
    dg.stop_generating()
