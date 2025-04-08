# Imports from the python standard library:
import json
import csv
import time
import threading
import struct
import os
import mmap
import logging

class PiccoloRP:
    def __init__(self):
        self._map_memory()

    def _map_memory(self):
        """Map the memory addresses from the FADS memory region to the FADS variables."""

        base_addr = 0x40600000
        map_size = 0x2000  # 8 KB mapping
        
        # Create a memory mapping of the FADS memory region
        mem_fd = open("/dev/mem", "r+b")
        self.mmap = mmap.mmap(mem_fd.fileno(), map_size, mmap.MAP_SHARED,
                                mmap.PROT_READ | mmap.PROT_WRITE, offset=base_addr)
        
        # Read the piccolo mmap json: contains the piccolo variables and their 
        # dtypes, addresses, units, and defaults
        script_dir = os.path.dirname(os.path.realpath(__file__))
        json_path = os.path.join(script_dir, "piccolo_mmap.json")
        
        with open(json_path, "r") as f:
            mmap_json = json.load(f)
        print("Top-level keys in mmap_json:", mmap_json.keys())

        # Assign the piccolo parameter information to the class attributes
        self.fads_parameters_info = mmap_json["fads_parameters"]
        self.droplet_parameters_info = mmap_json["droplet_parameters"]
        self.sort_gates_info = mmap_json["sort_gates"]

        print(self.sort_gates_info)

        self.mmap_info = (
            self.fads_parameters_info
            + self.droplet_parameters_info
            + self.sort_gates_info
        )
        print(self.mmap_info)

        print("Memory map completed.")
        
        return None
        
    def _interpret_dtype(self):
        """Interpret the data type from the JSON configuration."""
        # TODO: trying to implement this once the JSON file is available not when each variable is read
        # need to test this
        dtype_intepretter = {
            "32'd":  { "fmt": "<I", "bits": 32, "signed": False, "bool": False },
            "32'sd": { "fmt": "<i", "bits": 32, "signed": True,  "bool": False },
            "16'b":  { "fmt": "<H", "bits": 16, "signed": False, "bool": True  },
            "14'sd": { "fmt": "<h", "bits": 14, "signed": True,  "bool": False },
            "3'b":   { "fmt": "<B", "bits": 3,  "signed": False, "bool": True  },
            "2'b":   { "fmt": "<B", "bits": 2,  "signed": False, "bool": True  },
            "1'b":   { "fmt": "<B", "bits": 1,  "signed": False, "bool": True  }
            }
        for var in self.mmap_info:
            var_conf = self.mmap_info[var]
            dtype = var_conf["dtype"]
            if dtype in dtype_intepretter:
                self.mmap_info[var]["fmt"] = dtype_intepretter[dtype]["fmt"]
                self.mmap_info[var]["bits"] = dtype_intepretter[dtype]["bits"]
                self.mmap_info[var]["signed"] = dtype_intepretter[dtype]["signed"]
                self.mmap_info[var]["bool"] = dtype_intepretter[dtype]["bool"]
            else:
                raise ValueError(f"Unsupported data type: {dtype}")
            
        print("Data types interpreted.")

    def _read_memory_value(self, address, dtype, size, mask_int=None):
        """Helper function to read a single memory value from the specified address."""
        offset = int(address, 16)
        self.mem_map.seek(offset)
        data = self.mem_map.read(size)
        if len(data) != size:
            self.logger.error(f"Failed to read {size} bytes from address {address}.")
            return None
        value = struct.unpack(dtype, data)[0]
        if mask_int is not None:
            value = value & mask_int
            # For 14-bit registers (mask 0x3FFF), perform sign extension.
            if mask_int == 0x3FFF:
                if value & (1 << 13):
                    value = value - (1 << 14)
        return value
    
    def _convert_width(self, raw):
        """
        Convert clock cycles to milliseconds.
        The conversion factor is determined by the clock frequency: (clock_MHz * 1000) cycles per millisecond.
        """
        factor = self.clock_calibration * 1000  # cycles per millisecond
        if isinstance(raw, list):
            return [x / factor for x in raw]
        return raw / factor
    
    def _convert_intensity(self, raw, channel):
        """
        Convert raw intensity to volts using calibration parameters for the specified channel.
        """
        if channel not in self.voltage_calibration:
            raise ValueError(f"Calibration parameters for channel {channel} not found.")
        params = self.voltage_calibration[channel]
        return (raw - params["offset"]) * params["gain"] / params["buffer_size"]
    
    def _convert_area(self, raw, channel):
        """
        Convert raw area (clock cycles x raw intensity) to V·ms.
        First converts the raw value to volts, then converts clock cycles to milliseconds using the clock_MHz value.
        """
        if channel not in self.voltage_calibration:
            raise ValueError(f"Calibration parameters for channel {channel} not found.")
        params = self.voltage_calibration[channel]
        factor = self.clock_calibration * 1000  # cycles per millisecond
        return ((raw - params["offset"]) * params["gain"] / params["buffer_size"]) / factor
    
    def _get_calibration(self, config_path):
        """
        Reads calibration configuration from a JSON file and initializes calibration parameters.
        """
        with open(config_path, "r") as f:
            config = json.load(f)
        # Calibration parameters for voltage conversion.
        self.voltage_calibration = config.get("voltage_calibration", {})
        # Clock frequency in MHz for time conversions.
        self.clock_calibration = config.get("clock_MHz", 125)

    def read_memory(self, addr, dtype, size, mask_int=None):
        """
        Reads from memory using the precomputed size and mask.
        If addr is a list, reads each address separately and returns a list of values.
        """
        if isinstance(addr, list):
            values = []
            for a in addr:
                values.append(self._read_memory_value(a, dtype, size, mask_int))
            return values
        else:
            return self._read_memory_value(addr, dtype, size, mask_int)
        
     # Logging methods   
    def _initialize_csv(self):
        """Open the CSV file and write the header. For multi-channel variables, expand headers."""
        self.csv_file = open(self.csv_filename, "w", newline="")
        self.csv_writer = csv.writer(self.csv_file)
        header = ["timestamp_ms"]
        for var in self.log_var:
            var_conf = self.fads_var[var]
            if isinstance(var_conf["addr"], list):
                header.extend([f"{var}_ch{i+1}" for i in range(len(var_conf["addr"]))])
            else:
                header.append(var)
        self.csv_writer.writerow(header)
        self.csv_file.flush()
        print(f"Log file {self.csv_filename} initialized.")

    def update_logging(self):
        timestamp_ms = time.time() * 1e3  # Convert to microseconds.

        # Reintroduce droplet ID consistency check.
        droplet_conf = self.fads_var["droplet_id"]
        droplet_id_1 = self.read_memory(droplet_conf["addr"],
                                        droplet_conf["dtype"],
                                        droplet_conf["size"],
                                        droplet_conf.get("mask_int"))

        raw_values = {}
        # Read each log variable using its configuration.
        for var in self.log_var:
            var_conf = self.fads_var[var]
            raw_values[var] = self.read_memory(var_conf["addr"],
                                               var_conf["dtype"],
                                               var_conf["size"],
                                               var_conf.get("mask_int"))

        # Read droplet_id again.
        droplet_id_2 = self.read_memory(droplet_conf["addr"],
                                        droplet_conf["dtype"],
                                        droplet_conf["size"],
                                        droplet_conf.get("mask_int"))
        if droplet_id_1 != droplet_id_2:
            # self.logger.info("Droplet ID changed during read; skipping logging.")
            return  # Skip logging if droplet ID changed.


        # --- Conversion: Use the calibration object if conversion on PS is enabled ---
        if self.convert_flag:
            converted_values = {}
            for var in self.log_var:
                raw_val = raw_values.get(var)
                if var in ["cur_droplet_width", "min_width_thresh"]:
                    converted_values[var] = self.conversion.convert_width(raw_val)
                elif var in ["cur_droplet_intensity", "min_intensity_thresh"]:
                    if isinstance(raw_val, list):
                        conv = [self.conversion.convert_intensity(raw_val[0], "ch1")]
                        if len(raw_val) > 1:
                            conv.append(self.conversion.convert_intensity(raw_val[1], "ch2"))
                        converted_values[var] = conv
                    else:
                        converted_values[var] = self.conversion.convert_intensity(raw_val, "ch1")
                elif var in ["cur_droplet_area", "min_area_thresh"]:
                    if isinstance(raw_val, list):
                        conv = [self.conversion.convert_area(raw_val[0], "ch1")]
                        if len(raw_val) > 1:
                            conv.append(self.conversion.convert_area(raw_val[1], "ch2"))
                        converted_values[var] = conv
                    else:
                        converted_values[var] = self.conversion.convert_area(raw_val, "ch1")
                elif var in ["droplet_classification"]:
                    converted_values[var] = dtype(raw_val, '016b')
                else:
                    # No conversion for other variables.
                    converted_values[var] = raw_val
                
                log_values = converted_values
        else:
            log_values = raw_values

        # --- CSV Logging: Write the timestamp and values to the CSV file ---
        if self.csv_flag:
            # Build the CSV row using the (converted or raw) values.
            row = [timestamp_ms]
            for var in self.log_var:
                val = log_values.get(var)
                if isinstance(val, list):
                    row.extend(val)
                else:
                    row.append(val)

            self.csv_writer.writerow(row)
            self.csv_file.flush()
        
        # Update the latest log data with the timestamp and values
        self.latest_log_data = json.dumps({"timestamp_ms": timestamp_ms, **log_values})

    def start_logging(self):
        try:
            while not self._stop_event.is_set():
                self.update_logging()
                time.sleep(0.0001)
        except KeyboardInterrupt:
            self.logger.info("Logging interrupted by user.")
        finally:
            self.stop_logging()

    def stop_logging(self):
        self._stop_event.set()
        if self.csv_flag and hasattr(self, "csv_file") and not self.csv_file.closed:
            self.csv_file.close()
        self.logger.info("Logging stopped.")

if __name__ == "__main__":
    rp = PiccoloRP()
    rp._map_memory()
