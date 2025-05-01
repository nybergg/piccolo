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

        self.fpga_inputs = {}
        self.pending_inputs = {}
        self.client_socket = None
        self.acq_thread_started = False
        
        self._map_memory()
        self._get_mmap_info()
        self._set_defaults()
        
        
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

        # Extract paremeter information for fpga inputs and outputs
        fpga_inputs = mmap_json["fpga_inputs"]
        fpga_outputs = mmap_json["fpga_outputs"]

        # Join the parameter information into a single list
        self.mmap_info = (
            fpga_inputs
            + fpga_outputs
        )

        # Store a list of variable names for FADS, droplet, and sort gates
        self.fpga_input_names = [v["name"] for v in fpga_inputs]
        self.fpga_ouput_names = [v["name"] for v in fpga_outputs]

        # Transform the mmap_info to go from human-readable to python-interperable 
        self._expand_mmap_info()
        self._interpret_mmap_dtypes()
        
        # Create an mmap dictionary for easy lookup by variable name
        self.mmap_lookup = {var["name"]: var for var in self.mmap_info}
        
        # Debugging
        if self.verbose:
            print("Memory map information loaded and formatted.")
        if self.very_verbose:
            print("Created a lookup dict for mmap info with keys:")
            for var in self.mmap_lookup:
                print(var)
            print("List of FPGA Inputs:")
            for var in fpga_inputs:
                print(var)
            print("List of FPGA Outputs:")
            for var in fpga_outputs:
                print(var)

        return None
    
    def _expand_mmap_info(self):
        """Expand the mmap_info list to handle variables for multiple channels and addresses."""
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
    

    ################ Memory get and set methods ################
    def get_var(self, var_name):
        """Get a memory value from the specified address."""
        var_conf = self.mmap_lookup.get(var_name)

        if var_conf is None:
            raise ValueError(f"Variable {var_name} not found in list from piccolo_mmap.json")

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
            print(f"Got {var_name} from memory: {val}")
        
        return val
    
    def get_outputs(self):
        """Get FPGA outputs from memory."""
        if self.verbose:
            print("\n--------Getting FPGA outputs from memory--------")
        
        fpga_outputs = {}
        for var in self.fpga_ouput_names:
            val = self.get_var(var)
            fpga_outputs[var] = val

        # Debug
        if self.verbose:
            print("Done getting FPGA outputs from memory.")
        if self.very_verbose:
            print("FPGA outputs recieved from memory:")
            for var_name, val in fpga_outputs.items():
                print(f"{var_name}: {val}")

        self.fpga_outputs = fpga_outputs
        
        return None
    
    def get_inputs(self):
        """Get FPGA inputs from memory."""
        if self.verbose:
            print("\n--------Getting FPGA inputs from memory--------")

        fpga_inputs = {}
        for var in self.fpga_input_names:
            val = self.get_var(var)
            fpga_inputs[var] = val

        # Debug
        if self.verbose:
            print("Done getting FPGA inputs from memory.")
        if self.very_verbose:
            print("FPGA inputs recieved from memory:")
            for var_name, val in fpga_inputs.items():
                print(f"{var_name}: {val}")

        self.fpga_inputs = fpga_inputs

        return None
    
    def get_all(self):
        """Get all FPGA variables from mmap_info."""
        if self.verbose:
            print("\n--------Getting all FPGA variables from memory map--------")
        
        fpga_vars = {}
        for var in self.mmap_lookup:
            val = self.get_var(var)
            fpga_vars[var] = val            
        
        # Debug
        if self.verbose:
            print("Done reading all variables from memory.")
        if self.very_verbose:
            print("All variables read from memory:")
            for var_name, val in fpga_vars.items():
                print(f"{var_name}: {val}")

        self.fpga_vars = fpga_vars
        
        return None
    
    def set_var(self, var_name, value):
        """Set a memory value to the specified address."""
        var_conf = self.mmap_lookup.get(var_name)

        if var_conf is None:
            raise ValueError(f"Variable {var_name} not found in list from piccolo_mmap.json")

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
            print(f"Set {var_name} in memory: {val}")

        return None
    
    def _set_defaults(self):
        """Set the default values to the memory."""
        # TODO: could imagine this being removed from RP-local in the future when the server/client handling is more robust.
        
        # Debug
        if self.verbose:
            print("\n--------Setting default values to memory--------")

        for var in self.mmap_lookup.values():
            var_name = var["name"]
            default_value = var.get("default")
            
            if default_value is not None:
                self.set_var(var_name, default_value)

        # Debug
        if self.verbose:
            print("Done setting default values to memory map.")
    
        return None

    
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
        drop_id_preread = self.get_var("droplet_id")
        self.get_all()

        drop_id_postread = self.get_var("droplet_id")

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
            
            for var_name, val in self.fpga_vars.items():
                row.append(val)
                
                if self.very_verbose:
                    print(f"Logging {var_name}: {val}")

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
        
        if self.verbose:
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
        # Gets calibration configuration from a JSON file and initializes calibration parameters.
        # """
        # with open(config_path, "r") as f:
        #     config = json.load(f)
        # # Calibration parameters for voltage conversion.
        # self.voltage_calibration = config.get("voltage_calibration", {})
        # # Clock frequency in MHz for time conversions.
        # self.clock_calibration = config.get("clock_MHz", 125)
        
    
    ################ Oscilliscope methods ################
    def _get_adc_data(self, continuous=False):
        """Read the ADC data from the memory."""    
        dec = rp.RP_DEC_128
        acq_trig_sour = rp.RP_TRIG_SRC_NOW
        N = 4096 # 16384

        # Initialize Red Pitaya API
        rp.rp_Init()
        rp.rp_AcqReset()
        rp.rp_AcqSetDecimation(dec)

        if self.verbose:
            print("\n--------Acquiring ADC data--------")
        
        
        rp.rp_AcqSetTriggerSrc(acq_trig_sour)
    
        try:
            while True:  # Keep acquiring & streaming
                t0 = time.time()
                rp.rp_AcqStart()
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

                t1 = time.time()
                    
                if self.verbose:
                    print("ADC data acquired successfully.")
                if self.very_verbose:
                    # print first 20 values of each channel
                    print(f"Acquisition time: {t1 - t0:.2f} seconds")
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

    def _control_server(self, client):
        """ TCP server that manages shutdown command from client """
        try:
            while True:
                data = client.recv(16)
                if not data:
                    break
                opcode = struct.unpack("I", data[:4])[0]
                if opcode == 99:
                    print("Shutdown signal received. Exiting.")
                    os._exit(0)
                else:
                    print(f"[Control] Unknown opcode: {opcode}")
        finally:
            client.close()
            print("Control command server closed.")

        return None
    
    def _getadc_server(self, client):
        """ TCP server that streams CH1 and CH2 data from ADCs """
        
        # Start continuous ADC acquisition if not already started
        if not self.acq_thread_started:
            self.acq_thread_started = True
            thread = threading.Thread(target=self._get_adc_data, kwargs={"continuous": True}, daemon=True)
            thread.start()
        
        # Continuously stream ADC data to the client
        try:
            while True:
                # send the latest available data
                if hasattr(self, 'ch1_data') and hasattr(self, 'ch2_data'):
                    combined_data = self.ch1_data + self.ch2_data
                    client.sendall(struct.pack(f'{2*len(self.ch1_data)}f', *combined_data))
        except Exception as e:
            print(f"[ADCStream] Error: {e}")
        finally:
            client.close()
            print("ADC stream server closed.")

        return None
    
    def _getmem_server(self, client):
        """ TCP server that streams fpga outputs """
        
        # Continuously stream FPGA outputs to the client
        # TODO: consider running this in it's own thread to mirror the ADC server
        try:
            while True:
                self.get_all()
                msg = json.dumps(self.fpga_vars).encode()
                length = struct.pack("I", len(msg)).ljust(16, b'\x00')
                client.sendall(length + msg)
                time.sleep(0.1)  # or trigger-based
        except Exception as e:
            print(f"[MemStream] Error: {e}")
        finally:
            client.close()
            print("Memory stream server closed.")
        
        return None

    def _setmem_server(self, client):
        """ TCP server that gets/sets fpga inputs """
        try:
            while True:
                header = client.recv(16)
                if not header:
                    break

                msg_len = struct.unpack("I", header[:4])[0]
                msg = client.recv(msg_len)
                data = json.loads(msg.decode())
                var_name = data["name"]
                value = data["value"]
                
                self.set_var(var_name=var_name, value=value)  
        except Exception as e:
            print(f"[MemSet] Error: {e}")
        finally:
            client.close()
            print("Memory set server closed.")
        
        return None

    def _start_server(self, port, handler):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', port))
        sock.listen(1)

        while True:
            client, addr = sock.accept()
            print(f"[Port {port}] Connection from {addr}")
            thread = threading.Thread(target=handler, args=(client,), daemon=True)
            thread.start()

    def start_servers(self):
        servers = {
            5000: self._control_server,
            5001: self._getadc_server,
            5002: self._getmem_server,
            5003: self._setmem_server,
        }

        for port, handler in servers.items():
            thread = threading.Thread(target=self._start_server, args=(port, handler), daemon=True)
            thread.start()
            print(f"[Port {port}] Server started.")

        print("All servers running.")
        while True:
            time.sleep(0.01)  # keep main thread alive

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true", help="Enable verbose mode")
    parser.add_argument("--very_verbose", action="store_true", help="Enable very verbose mode")
    args = parser.parse_args()
    
    piccolo = PiccoloRP(verbose=args.verbose, very_verbose=args.very_verbose)
    
    # Test the logging
    # print("--------Testing logging--------")
    # piccolo._initialize_csv()
    # piccolo.start_logging()
    # print("Logging test completed.")

    
    # Test the memory mapping and reading/writing
    print("--------Testing memory mapping--------")
    piccolo.get_all()

    # Test the ADC data acquisition
    print("--------Testing ADC data acquisition--------")
    piccolo._get_adc_data()

    # Test the memory mapping and reading/writing
    print("--------Testing get/set--------")
    test_var = "min_width_thresh[0]"
    test_val = 200
    print(f"Testing get/set for {test_var} with test value of {test_val}...")
    
    val = piccolo.get_var(var_name = test_var)
    print(f"Got value of {val} for {test_var}")
    piccolo.set_var(var_name = test_var, value = test_val)
    print(f"Set value of {test_val} to {test_var}")
    val = piccolo.get_var(var_name = test_var)
    print(f"Reread value of {val} for {test_var}")

    # Reset variables back to defaults
    piccolo._set_defaults()
    piccolo.get_all()
    print("Reset variables to defaults")

    print("\n////////// All Red Pitaya Testing Complete ///////////")

    # Test servers
    print("--------Testing servers--------")
    piccolo.start_servers()

    
    