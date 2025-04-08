# Imports from the python standard library:
import json
import csv
import time
import threading
import struct
import os
import mmap
import logging
import argparse


class PiccoloRP:
    def __init__(self, verbose=False, very_verbose=False):
        self.verbose = verbose
        self.very_verbose = very_verbose
        self._map_memory()
        self._get_mmap_info()
    
    ##### Memory mapping methods #####
    def _map_memory(self):
        """Map the memory map region."""
        base_addr = 0x40600000
        map_size = 0x2000  # 8 KB mapping
        
        # Debugging
        if self.verbose:
            print("--------Mapping memory region--------")
        if self.very_verbose:
            print(f"Memory mapping at address {hex(base_addr)} with size {map_size} bytes...")

        # Create a memory mapping of the FADS memory region
        mem_fd = open("/dev/mem", "r+b")
        self.mmap = mmap.mmap(mem_fd.fileno(), map_size, mmap.MAP_SHARED,
                                mmap.PROT_READ | mmap.PROT_WRITE, offset=base_addr)
        
        # Debugging
        if self.verbose:
            print("Done mapping memory.")
        
        return None
    
    def _get_mmap_info(self):
        """Get information about the Piccolo variables and format for easy read/write."""
        # Debugging
        if self.verbose:
            print("--------Loading memory map information--------")
        
        # Load the JSON file containing the memory map information
        script_dir = os.path.dirname(os.path.realpath(__file__))
        json_path = os.path.join(script_dir, "piccolo_mmap.json")
        with open(json_path, "r") as f:
            mmap_json = json.load(f)

        # Extract paremeter information for FADS, droplet, and sort gates
        fads_parameters = mmap_json["fads_parameters"]
        droplet_parameters = mmap_json["droplet_parameters"]
        sort_gates = mmap_json["sort_gates"]

        # Join the parameter information into a single list
        self.mmap_info = (
            fads_parameters
            + droplet_parameters
            + sort_gates
        )

        # Format the mmap_info for easy read/write
        self._expand_mmap_info()
        self._interpret_mmap_dtypes()
        
        # Create an mmap dictionary for easy lookup by variable name
        self.mmap_lookup = {var["name"]: var for var in self.mmap_info}
        
        # Store a list of variable names for FADS, droplet, and sort gates
        self.fads_parameter_names = [v["name"] for v in fads_parameters]
        self.droplet_parameter_names = [v["name"] for v in droplet_parameters]
        self.sort_gate_names = [v["name"] for v in sort_gates]

        # Debugging
        if self.verbose:
            print("Memory map information loaded and formatted.")
        if self.very_verbose:
            print("Created a lookup dict for mmap info with keys:")
            for param in self.mmap_lookup:
                print(param)
            print("List of FADS Parameters:")
            for param in self.fads_parameter_names:
                print(param)
            print("List of Droplet Parameters:")
            for param in self.droplet_parameter_names:
                print(param)
            print("List of Sort Gates:")
            for param in self.sort_gate_names:
                print(param)

        return None
    
    def _expand_mmap_info(self):
        """Expand the mmap_info list to handle variables with multiple addresses."""
        expanded_info = []

        for var in self.mmap_info:
            addr = var["addr"]

            # If it's a list of addresses, split into separate entries
            if isinstance(addr, list):
                defaults = var.get("default", [None] * len(addr))
                for i, (a, d) in enumerate(zip(addr, defaults)):
                    new_var = var.copy()
                    new_var["name"] = f"{var['name']}[{i}]"
                    new_var["addr"] = a
                    if isinstance(defaults, list):
                        new_var["default"] = d
                    expanded_info.append(new_var)
            else:
                expanded_info.append(var)

        self.mmap_info = expanded_info
        
        # Debugging
        if self.verbose:
            print("Memory map info expanded.")
        if self.very_verbose:
            print("Expanded mmap_info:")
            for var in self.mmap_info:
                print(var)

        return None

    def _interpret_mmap_dtypes(self):
        """Interpret the Verilog datatypes in the JSON file and convert them to Python datatypes."""
        dtype_intepretter = {
            "32'd":  { "fmt": "<I", "bits": 32, "signed": False, "bool": False },
            "32'sd": { "fmt": "<i", "bits": 32, "signed": True,  "bool": False },
            "16'b":  { "fmt": "<H", "bits": 16, "signed": False, "bool": True  },
            "14'sd": { "fmt": "<h", "bits": 14, "signed": True,  "bool": False },
            "3'b":   { "fmt": "<B", "bits": 3,  "signed": False, "bool": True  },
            "2'b":   { "fmt": "<B", "bits": 2,  "signed": False, "bool": True  },
            "1'b":   { "fmt": "<B", "bits": 1,  "signed": False, "bool": True  }
            }

        # Update variables with their corresponding Python data types
        for var in self.mmap_info:
            dtype = var.get("dtype")
            if dtype in dtype_intepretter:
                var.update(dtype_intepretter[dtype])
            else:
                raise ValueError(f"Unsupported data type: {dtype}")
            
        # Debug
        if self.verbose:
            print("Data types interpreted.")
        if self.very_verbose:
            print("Interpreted datatypes for mmap_info:")
            for var in self.mmap_info:
                print(var)
            
        return None
    

    ##### Memory reading and writing methods #####
    def read_memory_all(self):
        """Read all variables from mmap_info."""
        if self.verbose:
            print("--------Reading all variables from memory map--------")
        
        all_values = {}
        for var in self.mmap_info:
            var_name = var["name"]
            val = self.read_memory_var(var_name)
            all_values[var["name"]] = val            
        
        self.all_values = all_values

        # Debug
        if self.verbose:
            print("Done reading all variables from memory mapped region.")
        if self.very_verbose:
            print("All variables read from memory mapped region:")
            for var_name, val in all_values.items():
                print(f"{var_name}: {val}")
        
        return None
    
    def read_memory_var(self, var_name):
        """Read a memory value from the specified address."""
        var_conf = self.mmap_lookup.get(var_name)

        if var_conf is None:
            raise ValueError(f"Variable {var_name} not found in Piccolo variables.")

        offset = int(var_conf["addr"], 16) if isinstance(var_conf["addr"], str) else var_conf["addr"]
        fmt = var_conf["fmt"]
        bits = var_conf["bits"]
        is_signed = var_conf["signed"]
        is_bool = var_conf["bool"]
        
        # Get the address and offset
        self.mmap.seek(offset)
        data = self.mmap.read(4) # Read block is always 4 bytes on RP
        
        # Determine the minimal size required for this format
        var_size = struct.calcsize(fmt)

        # Use only the variable-specific bytes from the 4-byte block.
        var_data = data[:var_size]
        val = struct.unpack(fmt, var_data)[0]

        # If smaller than the struct size, mask and sign-extend if needed
        actual_bits = var_size * 8
        if bits < actual_bits: 
            mask = (1 << bits) - 1 # e.g., for 14 bits, mask = 0x3FFF
            val &= mask
            if is_signed:
                sign_bit = 1 << (bits - 1)
                if val & sign_bit:
                    val -= (1 << bits)

        if is_bool:
            val = bin(val)[2:] #convert to binary string  
        
        return val


    ##### Logging methods #####
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

    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true", help="Enable verbose mode")
    parser.add_argument("--very_verbose", action="store_true", help="Enable very verbose mode")
    args = parser.parse_args()
    
    rp = PiccoloRP(verbose=args.verbose, very_verbose=args.very_verbose)
    rp.read_memory_all()

