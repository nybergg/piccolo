# Imports from the python standard library:
import json
import csv
import time
import threading
import struct
import os
import mmap
import argparse
import socket

# Red Pitaya API imports
import sys
sys.path.append("/opt/redpitaya/lib/python")
import rp  # Your Red Pitaya API module


class PiccoloRP:
    def __init__(self, verbose=False, very_verbose=False):
        self.verbose = verbose
        self.very_verbose = very_verbose
        self.stop_event = False
        self.csv_flag = True
        self._map_memory()
        self._get_mmap_info()
        self._write_defaults()
        self.client_socket = None
    
    ################ Memory mapping methods ################
    def _map_memory(self):
        """Map the memory map region."""
        base_addr = 0x40600000
        map_size = 0x2000  # 8 KB mapping
        
        # Debugging
        if self.verbose:
            print("\n--------Mapping memory region--------")
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
            print("\n--------Loading memory map information--------")
        
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
        """Interpret the Verilog datatypes as Python datatypes."""
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
    

    ################ Memory read and write methods ################
    def read_var(self, var_name):
        """Read a memory value from the specified address."""
        var_conf = self.mmap_lookup.get(var_name)

        if var_conf is None:
            raise ValueError(f"Variable {var_name} not found in piccolo variables.")

        offset = int(var_conf["addr"], 16)
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

        # Debug
        if self.very_verbose:
            print(f"Read {var_name} from memory: {val}")
        
        return val
    
    def read_drop_params(self):
        """Read droplet parameters from memory."""
        if self.verbose:
            print("\n--------Reading droplet parameters from memory--------")
        
        droplet_parameters = {}
        for var in self.droplet_parameter_names:
            val = self.read_var(var)
            droplet_parameters[var] = val

        # Debug
        if self.verbose:
            print("Done reading droplet parameters from memory.")
        if self.very_verbose:
            print("Droplet parameters read from memory:")
            for var_name, val in droplet_parameters.items():
                print(f"{var_name}: {val}")

        self.droplet_parameters = droplet_parameters
        
        return None
    
    def read_fads_params(self):
        """Read FADS parameters from memory."""
        if self.verbose:
            print("\n--------Reading FADS parameters from memory--------")

        fads_params = {}
        for var in self.fads_parameter_names:
            val = self.read_var(var)
            fads_params[var] = val

        # Debug
        if self.verbose:
            print("Done reading FADS parameters from memory.")
        if self.very_verbose:
            print("FADS parameters read from memory:")
            for var_name, val in fads_params.items():
                print(f"{var_name}: {val}")

        self.fads_params = fads_params

        return None
    
    def read_sort_gates(self):
        """Read sort gates from memory."""
        if self.verbose:
            print("\n--------Reading sort gates from memory--------")

        sort_gates = {}
        for var in self.sort_gate_names:
            val = self.read_var(var)
            sort_gates[var] = val

        # Debug
        if self.verbose:
            print("Done reading sort gates from memory.")
        if self.very_verbose:
            print("Sort gates read from memory:")
            for var_name, val in sort_gates.items():
                print(f"{var_name}: {val}")

        self.sort_gates = sort_gates

        return None
    
    def read_all(self):
        """Read all variables from mmap_info."""
        if self.verbose:
            print("\n--------Reading all variables from memory map--------")
        
        all_values = {}
        for var in self.mmap_lookup:
            val = self.read_var(var)
            all_values[var] = val            
        
        self.all_values = all_values

        # Debug
        if self.verbose:
            print("Done reading all variables from memory.")
        if self.very_verbose:
            print("All variables read from memory:")
            for var_name, val in all_values.items():
                print(f"{var_name}: {val}")
        
        return None
    
    def write_var(self, var_name, value):
        """Write a memory value to the specified address."""
        var_conf = self.mmap_lookup.get(var_name)

        if var_conf is None:
            raise ValueError(f"Variable {var_name} not found in piccolo variables.")

        offset = int(var_conf["addr"], 16) 
        fmt = var_conf["fmt"]
        bits = var_conf["bits"]
        is_bool = var_conf["bool"]

        # For binary (bool) types, interpret the value as a binary literal.
        if is_bool:
            # If value is not a string, convert it to string
            val = int(value, 2)
        else:
            val = value

        # Ensure the value fits in the declared bits.
        if bits < struct.calcsize(fmt) * 8:
            mask = (1 << bits) - 1
            val &= mask

        # Pack the value into the minimal number of bytes.
        packed_val = struct.pack(fmt, val)
        # Create a full 4-byte block (all zeros)
        block = bytearray(4)
        # Insert the packed value into the beginning of the block.
        block[:len(packed_val)] = packed_val

        # Write the 4-byte block to memory.
        self.mmap.seek(offset)
        self.mmap.write(block)

        # Debug
        if self.verbose:
            print(f"Wrote {var_name} to memory: {val}")

        return None
    
    def _write_defaults(self):
        """Write the default values to the memory."""

        # Debug
        if self.verbose:
            print("\n--------Writing default values to memory--------")

        for var in self.mmap_lookup.values():
            var_name = var["name"]
            default_value = var.get("default")
            
            if default_value is not None:
                self.write_var(var_name, default_value)

        # Debug
        if self.verbose:
            print("Done writing default values to memory map.")
    
        return None
    
    # def _write_sort_gates(self):
    #     """Write sort gates to memory."""
    #     # TODO: broken method need to clean up
    #     # Debug
    #     if self.verbose:
    #         print("\n--------Writing sort gates to memory--------")

    #     for var in self.sort_gate_names:
    #         val = self.sort_gates(var)
    #         self.write_var(var, val)

    #     # Debug
    #     if self.verbose:
    #         print("Done writing default values to memory map.")
    
    #     return None
    
    ################ Logging methods ################
    def _initialize_csv(self):
        """Open the CSV file and write the header. For multi-channel variables, expand headers."""
        if self.verbose:
            print("\n--------Initializing CSV logging--------")
        
        # Log file name with timestamp
        csv_filename = f"piccolo_log_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        self.csv_filename = os.path.join(os.getcwd(), csv_filename)

        # Initialize the CSV file
        self.csv_file = open(self.csv_filename, "w", newline="")
        self.csv_writer = csv.writer(self.csv_file)
        header = ["timestamp_ms"]
        
        for var in self.mmap_lookup:
            header.append(var)
        self.csv_writer.writerow(header)
        self.csv_file.flush()
        print(f"Log file {self.csv_filename} initialized.")

    def _update_logging(self):
        timestamp_ms = time.time() * 1e3  # Convert to microseconds.

        if self.verbose:
            print("\n--------Updating log values--------")

        # Read droplet ID from memory.
        drop_id_preread = self.read_var("droplet_id")
        self.read_all()

        drop_id_postread = self.read_var("droplet_id")

        if drop_id_preread != drop_id_postread:
            if self.very_verbose:
                print("Dropping log values due to droplet ID change.")
            return  # Skip logging if droplet ID changed.

        # --- CSV Logging: Write the timestamp and values to the CSV file ---
        if self.csv_flag:
            # Build the CSV row using the (converted or raw) values.
            if self.verbose:
                print("Writing droplet parameters to CSV file...")
            row = [timestamp_ms]
            for var in self.mmap_lookup:
                val = self.all_values[var]
                row.append(val)

            self.csv_writer.writerow(row)
            self.csv_file.flush()
        

    def start_logging(self):
        if self.verbose:
            print("\n--------Starting logging--------")
        duration = 3  # seconds
        start_time = time.time()
        try:
            while time.time() - start_time < duration:
                self._update_logging()
                time.sleep(0.00011)
        except KeyboardInterrupt:
            print("Logging interrupted by user.")
        finally:
            self.stop_logging()

    def stop_logging(self):
        self.stop_event = True
        self.csv_file.close()
        print("Logging stopped.")

    # def _convert_width(self, raw):
    #     """
    #     Convert clock cycles to milliseconds.
    #     The conversion factor is determined by the clock frequency: (clock_MHz * 1000) cycles per millisecond.
    #     """
    #     factor = self.clock_calibration * 1000  # cycles per millisecond
    #     if isinstance(raw, list):
    #         return [x / factor for x in raw]
    #     return raw / factor
    
    # def _convert_intensity(self, raw, channel):
    #     """
    #     Convert raw intensity to volts using calibration parameters for the specified channel.
    #     """
    #     if channel not in self.voltage_calibration:
    #         raise ValueError(f"Calibration parameters for channel {channel} not found.")
    #     params = self.voltage_calibration[channel]
    #     return (raw - params["offset"]) * params["gain"] / params["buffer_size"]
    
    # def _convert_area(self, raw, channel):
    #     """
    #     Convert raw area (clock cycles x raw intensity) to V·ms.
    #     First converts the raw value to volts, then converts clock cycles to milliseconds using the clock_MHz value.
    #     """
    #     if channel not in self.voltage_calibration:
    #         raise ValueError(f"Calibration parameters for channel {channel} not found.")
    #     params = self.voltage_calibration[channel]
    #     factor = self.clock_calibration * 1000  # cycles per millisecond
    #     return ((raw - params["offset"]) * params["gain"] / params["buffer_size"]) / factor
    
    # def _get_calibration(self, config_path):
        # """
        # Reads calibration configuration from a JSON file and initializes calibration parameters.
        # """
        # with open(config_path, "r") as f:
        #     config = json.load(f)
        # # Calibration parameters for voltage conversion.
        # self.voltage_calibration = config.get("voltage_calibration", {})
        # # Clock frequency in MHz for time conversions.
        # self.clock_calibration = config.get("clock_MHz", 125)
        
    
    ################ Oscilliscope methods ################
    def _get_ADC_data(self, continuous=False):
        """Read the ADC data from the memory."""    
        dec = rp.RP_DEC_64
        trig_dly = 8191
        acq_trig_sour = rp.RP_TRIG_SRC_NOW
        N = 16384

        # Initialize Red Pitaya API
        rp.rp_Init()
        rp.rp_AcqReset()
        rp.rp_AcqSetDecimation(dec)
        rp.rp_AcqSetTriggerDelay(trig_dly)
    
        try:
            while True:  # Keep acquiring & streaming
                if self.verbose:
                    print("\n--------Acquiring ADC data--------")
                
                rp.rp_AcqStart()
                rp.rp_AcqSetTriggerSrc(acq_trig_sour)

                # Wait for trigger
                while rp.rp_AcqGetTriggerState()[1] != rp.RP_TRIG_STATE_TRIGGERED:
                    time.sleep(0.1)  # Avoid CPU overuse

                # Fill state
                while 1:
                    if rp.rp_AcqGetBufferFillState()[1]:
                        break

                # Get new data from ADC
                ch1_buffer = rp.fBuffer(N)
                ch2_buffer = rp.fBuffer(N)
                rp.rp_AcqGetLatestDataV(rp.RP_CH_1, N, ch1_buffer)
                rp.rp_AcqGetLatestDataV(rp.RP_CH_2, N, ch2_buffer)

                # Convert to list for streaming
                ch1_data = [ch1_buffer[i] for i in range(N)]
                ch2_data = [ch2_buffer[i] for i in range(N)]

                # Store the data as attribute to class
                self.ch1_data = ch1_data
                self.ch2_data = ch2_data

                if self.client_socket is not None:
                    self.client_socket.sendall(struct.pack(f'{N}f', *ch1_data))
                    self.client_socket.sendall(struct.pack(f'{N}f', *ch2_data))


                if self.verbose:
                    print("ADC data acquired successfully.")
                if self.very_verbose:
                    # print first 20 values of each channel
                    print("First 20 values of ADC 1 data:", ch1_data[:20])
                    print("First 20 values of ADC 2 data:", ch2_data[:20])

                if not continuous:
                    break
                                 

        except (BrokenPipeError, ConnectionResetError):
            print("Client disconnected.")
        except Exception as e:
            print(f"Error acquiring signals: {e}")
        finally:
            rp.rp_Release()
            print("Red Pitaya resources released.")
    
        return None
    

    ################ Server methods ################
    def _adc_server(self):
        """ TCP server that streams ADC data to a connected client """
        tcp_port = 5000
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('', tcp_port))
        server_socket.listen(1)
        print(f"TCP server listening on port {tcp_port}")

        while True:
            self.client_socket, addr = server_socket.accept()
            print(f"Connection accepted from {addr}")

            try:
                while True:
                    header = self.client_socket.recv(16)
                    if not header:
                        print("Client disconnected.")
                        break

                    opcode = struct.unpack("I", header[:4])[0]

                    if opcode == 3:
                        self._get_ADC_data(continuous=False)  # Stream once per command
                    elif opcode == 99:  # Shutdown opcode
                        print("Shutdown command received. Exiting server loop.")
                        return
                    else:
                        print(f"Unknown opcode received: {opcode}")
            except Exception as e:
                print(f"Error in server loop: {e}")
            finally:
                if self.client_socket:
                    self.client_socket.close()
                    print("Client connection closed.")


    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true", help="Enable verbose mode")
    parser.add_argument("--very_verbose", action="store_true", help="Enable very verbose mode")
    args = parser.parse_args()
    
    piccolo = PiccoloRP(verbose=args.verbose, very_verbose=args.very_verbose)

    # Test the memory mapping and reading/writing
    print("--------Testing memory mapping--------")
    piccolo.read_all()

    # Test the ADC data acquisition
    print("--------Testing ADC data acquisition--------")
    piccolo._get_ADC_data()

    # Test ADC server
    piccolo._adc_server()
    
    # test_var = "min_width_thresh[0]"
    # test_val = 100
    # print(f"Testing read/write for {test_var} with test value of {test_val}...")
    
    # val = rp.read_var(var_name = test_var)
    # print(f"Read value of {val} for {test_var}")
    # rp.write_var(var_name = test_var, value = test_val)
    # print(f"Wrote value of {test_val} to {test_var}")
    # val = rp.read_var(var_name = test_var)
    # print(f"Reread value of {val} for {test_var}")

    # Test the logging
    # print("--------Testing logging--------")
    # rp._initialize_csv()
    # rp.start_logging()
    # print("Logging test completed.")

    print("\n////////// All Red Pitaya Testing Complete ///////////")
    