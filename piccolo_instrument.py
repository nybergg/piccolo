import os
import json
import paramiko
from scp import SCPClient
import threading
import socket
import numpy as np
import re
import time
import posixpath
import pandas as pd

# Import piccolo clients
from piccolo_clients import (
    ADCStreamClient,
    MemoryStreamClient,
    MemoryCommandClient,
    ControlCommandClient
)

class Instrument:
    def __init__(self, 
                 local_script="piccolo_rp.py",
                 local_dir="redpitaya", 
                 script_args=None, 
                 rp_dir="piccolo_testing",
                 verbose=False,
                 very_verbose=False,
                 debug_flag=False 
                 ):
        
        # Local and remote script information
        self.local_script = local_script
        self.local_dir = local_dir
        self.script_args = script_args or []
        self.rp_dir = rp_dir
        self.rp_output = []  

        # Verbosity levels and debug flag
        self.verbose = verbose
        self.very_verbose = very_verbose
        self.debug_flag = debug_flag

        # Get rp login information
        self.get_rp_login()

        # Get calibration values
        self.get_rp_calibration()
        
        # Setup clients
        self.setup_clients()

        # Setup droplet data buffer
        self.buffer_size = 1000  # or set from UI
        self.droplet_data = pd.DataFrame()
        self.adc1_data = []
        self.adc2_data = []
        self.adc3_data = []
        self.adc4_data = []

        # FPGA register cache
        self.fpga_registers = {
            "fads_reset": 0,
            "sort_delay": 100,
            "sort_duration": 50,
            "sort_enable": 1,
            "enabled_channels": 15,
            "droplet_sensing_addr": 0,
        }
        for i in range(4):
            self.fpga_registers[f"min_intensity_thresh[{i}]"] = -175
            self.fpga_registers[f"low_intensity_thresh[{i}]"] = -150
            self.fpga_registers[f"high_intensity_thresh[{i}]"] = 900
            self.fpga_registers[f"min_width_thresh[{i}]"] = 1250
            self.fpga_registers[f"low_width_thresh[{i}]"] = 12500
            self.fpga_registers[f"high_width_thresh[{i}]"] = 0xccddeeff
            self.fpga_registers[f"min_area_thresh[{i}]"] = 1
            self.fpga_registers[f"low_area_thresh[{i}]"] = 255
            self.fpga_registers[f"high_area_thresh[{i}]"] = 0xccddeeff




    ################ Red Pitaya Setup and Run Methods ################

    def get_rp_login(self):
        """ Get the local information for the Red Pitaya and run the script on it"""
        
        # Load the Red Pitaya login information from a JSON file
        with open("redpitaya/rp_login_4CH.json", "r") as f:
            rp_login_json = json.load(f)

        self.ip = rp_login_json["ip"]
        self.username = rp_login_json["username"]
        self.password = rp_login_json["password"]
        
        # Debug
        if self.verbose:
            print("\nRed Pitaya login information loaded successfully")
        if self.very_verbose:
            print(f"IP: {self.ip}")
            print(f"Username: {self.username}")
            print(f"Password: {self.password}")

        return self.ip, self.username, self.password
    
    
    def get_rp_calibration(self):
        """Hardcode the Red Pitaya calibration values for CH1 and CH2"""
        calibration_values = {}
        calibration_values["CH1"] = [-10, 1.0]
        calibration_values["CH2"] = [-10, 1.0]
        calibration_values["CH3"] = [-10, 1.0] # Placeholder, adjust as needed
        calibration_values["CH4"] = [-10, 1.0] # Placeholder, adjust as needed

        self.calibration_values = calibration_values

        # Debug
        if self.verbose:
            print("\nRed Pitaya calibration values loaded successfully")
        if self.very_verbose:
            print(f"Calibration values: {calibration_values}")

        return self.calibration_values
            
    
    def launch_piccolo_rp(self):
        """ Get the local information for the Red Pitaya and run the script on it"""

        # Connect to the Red Pitaya and add directory if missing
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, username=self.username, password=self.password)
        ssh.exec_command(f"mkdir -p {self.rp_dir}")
        
        # Debug
        if self.verbose:
            print("\nConnected to Red Pitaya successfully")
        
        # Transfer local directory to the Red Pitaya
        with SCPClient(ssh.get_transport()) as scp:
            for root, _, files in os.walk(self.local_dir):
                for file in files:
                    local_path = os.path.join(root, file)
                    remote_path = posixpath.join(self.rp_dir, file)  # Remote: needs Linux-style slashes
                    scp.put(local_path, remote_path)

                    if self.very_verbose:
                        print(f"Local file {local_path} transferred to Red Pitaya {remote_path}")

        # Debug
        if self.verbose:
            print(f"\nFiles transferred to Red Pitaya.")
        
        if not self.debug_flag:
            # Construct command for background piccolo_rp.py process with logging
            args = " ".join(self.script_args)
            cmd = (
                f'cd {self.rp_dir} && ' 
                f'nohup sudo python3 {self.local_script} {args} ' 
                f'> piccolo_stdout.log 2> piccolo_stderr.log < /dev/null &'
            )

            # Launch in background
            ssh.exec_command(f'bash -c "{cmd}"')

            if self.verbose:
                print("\nScript launched in background. Use log files to monitor.")

        else:
            # Construct command for foreground piccolo_rp.py process for debugging
            args = " ".join(self.script_args)
            cmd = f'bash -l -c "cd {self.rp_dir} && sudo python3 {self.local_script} {args}"'
            _, stdout, stderr = ssh.exec_command(cmd, get_pty=True)

            # Read stdout in real-time
            try:
                for line in iter(stdout.readline, ""):
                    line = line.strip()
                    if line:
                        self.rp_output.append(line)
                        if self.very_verbose:
                            print(f"[RP stdout] {line}")
            except Exception as e:
                print(f"[Paramiko stdout read error] {e}")

            # Ensure command completed
            _ = stdout.channel.recv_exit_status() 
            
            # Capture any final stdout and stderr output
            self.stdout = stdout.read().decode().strip()
            self.stderr = stderr.read().decode().strip()

            # Debug
            if self.verbose:
                print("\nScript executed. SSH channel closed.")
        
        # Close connection to Red Pitaya
        ssh.close()

        return None


    ################ Red Pitaya Client Methods ################

    def setup_clients(self):
        """Initialize but don't start clients yet."""
        self.adc_stream_client = ADCStreamClient(
            data_callback=self._get_adc_data)
        self.memory_stream_client = MemoryStreamClient(
            data_callback=self._get_memory_data)
        self.memory_command_client = MemoryCommandClient()
        self.control_command_client = ControlCommandClient()


    def start_clients(self):
        """Start all Red Pitaya clients."""
        self.adc_stream_client.start(self.ip)
        self.memory_stream_client.start(self.ip)
        self.memory_command_client.start(self.ip)
        print("[Instrument] All clients started.")       


    def stop_clients(self):
        """Stop all clients."""
        self.adc_stream_client.stop()
        self.memory_stream_client.stop()
        self.memory_command_client.stop()
        print("[Instrument] All clients stopped.")


    def set_memory_variable(self, variable, value):
        """Set FPGA memory variable."""
        self.memory_command_client.send_set_command(variable, value)
        print(f"[Instrument] Queued memory variable set: {variable} = {value}")
        # Update internal cache
        if variable in self.fpga_registers:
            self.fpga_registers[variable] = value

    def get_fpga_registers(self):
        """Return the cached dictionary of FPGA register values."""
        return self.fpga_registers

    def get_fpga_registers_converted(self):
        """
        Return a dictionary of FPGA registers with human-readable values and units.
        Returns a dictionary where each value is a tuple: (converted_value, unit_string).
        """
        display_registers = {}
        raw_registers = self.get_fpga_registers()

        for name, value in raw_registers.items():
            # Default: no conversion
            display_value = value
            unit = ""

            # Try to extract channel number
            ch_match = re.search(r'\[(\d)\]', name)
            ch = int(ch_match.group(1)) if ch_match else None

            try:
                # Ensure value is a number for conversions
                numeric_value = int(value)

                if ch is not None:
                    if 'intensity_thresh' in name:
                        display_value = self.convert_raw_to_volts(numeric_value, ch)
                        unit = "V"
                    elif 'area_thresh' in name:
                        # Based on cur_droplet_area conversion
                        display_value = self.convert_raw_to_volts(numeric_value, ch) / 1000.0
                        unit = "V·ms"
                    elif 'width_thresh' in name:
                        # Based on cur_droplet_width conversion, raw is in us
                        display_value = numeric_value / 1000.0
                        unit = "ms"
                elif 'sort_delay' in name or 'sort_duration' in name:
                    # Assuming these are in microseconds
                    display_value = numeric_value / 1000.0
                    unit = "ms"
                elif name == 'droplet_frequency':
                    if numeric_value != 0:
                        display_value = int(1e6 / numeric_value)  # Convert from us period to Hz frequency
                        unit = "Hz"
                    else:
                        display_value = 0  # Avoid division by zero                    else:
                        unit = "Hz"
            except (ValueError, TypeError):
                # Value is not a number (e.g., binary string from get_var), keep as is
                display_value = value
                unit = ""

            display_registers[name] = (display_value, unit)

        return display_registers

    def enable_sorter(self, enable: bool):
        """Enable or disable the droplet sorter on the FPGA."""
        value_to_set = 1 if enable else 0
        self.set_memory_variable("sort_enable", value_to_set)
        status = "enabled" if enable else "disabled"
        print(f"[Instrument] Sorter has been {status}.")


    def stop_servers(self):
        """Send kill command to Red Pitaya."""
        self.control_command_client.start(self.ip)
        time.sleep(1)  # Give time for kill to be sent
        self.control_command_client.stop()
        print("[Instrument] Red pitaya methods shut down successfully.")

    
    ################ Red Pitaya ADC Data Handling Methods ################

    def _get_adc_data(self, adc1_data, adc2_data, adc3_data, adc4_data):
        self.adc1_data = adc1_data
        self.adc2_data = adc2_data
        self.adc3_data = adc3_data
        self.adc4_data = adc4_data

        return self.adc1_data, self.adc2_data, self.adc3_data, self.adc4_data

    def _get_memory_data(self, fpgaoutput):
        if not fpgaoutput:
            return
        
        # Update the FPGA register cache with the latest values
        self.fpga_registers.update(fpgaoutput)
        if self.very_verbose:
            print(f"[Instrument] Received memory data: {fpgaoutput}")

        try:
            row = fpgaoutput

            for ch in range(4):

                # Intensity
                raw_int = fpgaoutput[f"cur_droplet_intensity[{ch}]"]
                row[f"cur_droplet_intensity[{ch}]"] = raw_int
                row[f"cur_droplet_intensity_v[{ch}]"] = self.convert_raw_to_volts(raw_int, ch)

                # Area
                raw_area = fpgaoutput[f"cur_droplet_area[{ch}]"]
                row[f"cur_droplet_area[{ch}]"] = raw_area
                row[f"cur_droplet_area_vms[{ch}]"] = self.convert_raw_to_volts(raw_area, ch) / 1000.0

                # Width
                raw_width = fpgaoutput[f"cur_droplet_width[{ch}]"]
                row[f"cur_droplet_width[{ch}]"] = raw_width
                row[f"cur_droplet_width_ms[{ch}]"] = raw_width / 1000.0

            # Append to DataFrame
            self.droplet_data = pd.concat([self.droplet_data, pd.DataFrame([row])], ignore_index=True)

            # Maintain rolling size
            if len(self.droplet_data) > self.buffer_size:
                self.droplet_data = self.droplet_data.iloc[-self.buffer_size:]

        except Exception as e:
            print(f"[Instrument] Error parsing droplet data: {e}")

        return self.droplet_data

    def save_droplet_data_log(self, filename="droplet_log.csv"):
        self.droplet_data.to_csv(filename, index=False)
        return None
    
    # In  Instrument or DummyInstrument class
    def save_adc_log(self, filename="adc_log.csv"):
        # Assuming adc1_data and adc2 _data have 4096 points
        time_data = np.linspace(0, 50, 4096)
        adc_data = {'time': time_data,
                    'adc1': self.adc1_data,
                    'adc2': self.adc2_data,
                    'adc3': self.adc3_data,
                    'adc4': self.adc4_data}
        df = pd.DataFrame({k: v for k, v in adc_data.items() if v is not None and len(v) == len(time_data)})
        df.to_csv(filename, index=False)
    
    
    def set_gate_limits(self, sort_keys, limits):
        if self.verbose:
            print(f"[Instrument] Recieved gate limits to set: {limits}")

        sort_gates = {}

        for i, key in enumerate(sort_keys):
            # Parse channel index
            ch = int(key[key.find('[')+1:key.find(']')])

            # Select x/y based on index
            low_coord = 'x0' if i == 0 else 'y0'
            high_coord = 'x1' if i == 0 else 'y1'
            low_val = limits[low_coord][0]
            high_val = limits[high_coord][0]

            # Convert if needed
            if "_vms" in key:
                low_val = int(self.convert_volts_to_raw(low_val, ch) * 1000)
                high_val = int(self.convert_volts_to_raw(high_val, ch) * 1000)
            elif "_ms" in key:
                low_val = int(low_val * 1000)
                high_val = int(high_val * 1000)
            elif "_v" in key:
                low_val = self.convert_volts_to_raw(low_val, ch)
                high_val = self.convert_volts_to_raw(high_val, ch)

            # Determine parameter type
            if "intensity" in key:
                param = "intensity"
            elif "width" in key:
                param = "width"
            elif "area" in key:
                param = "area"
            else:
                raise ValueError(f"Unrecognized key: {key}")

            sort_gates[f"low_{param}_thresh[{ch}]"] = low_val
            sort_gates[f"high_{param}_thresh[{ch}]"] = high_val

        if self.verbose:
            print(f"[Instrument] Setting sort gates: {sort_gates}")
        
        # Write sort_gates to FPGA memory
        for var, val in sort_gates.items():
            self.set_memory_variable(var, int(val))

        # Save for inspection
        self.sort_gates = sort_gates
        
        return self.sort_gates
    

    def set_detection_threshold(self, thresh, thresh_key = "min_intensity_thresh[0]"):

        if self.verbose:
            print(f"[Instrument] Setting detection threshold for {thresh_key}: {thresh_key}")
        
        ch = int(thresh_key[thresh_key.find('[')+1:thresh_key.find(']')])
        thresh_raw = self.convert_volts_to_raw(thresh, ch)    

        # Write sort_gates to FPGA memory
        self.set_memory_variable(thresh_key, int(thresh_raw))
        
        return thresh
    
    def convert_raw_to_volts(self, raw_value, ch):
        """Convert raw ADC value to volts using calibration values."""
        vp = 20.0  # 40V peak-to-peak
        adc_max = 8192.0  # Max ADC value
        ch_key = f"CH{ch+1}"
        offset, gain = self.calibration_values[ch_key]
        volt_value = (raw_value - offset) * gain / adc_max * vp
        
        return volt_value
    
    def convert_volts_to_raw(self, volt_value, ch):
        """Convert volts to raw ADC value using calibration values."""
        vp = 20.0  # 40V peak-to-peak
        adc_max = 8192.0  # Max ADC value
        ch_key = f"CH{ch+1}"
        offset, gain = self.calibration_values[ch_key]
        raw_value = (volt_value * adc_max / vp) / gain + offset
        
        return int(raw_value)

if __name__ == "__main__":
    instrument = Instrument(
        local_script="piccolo_rp.py",
        local_dir="redpitaya",
        script_args=["--verbose", "--very_verbose"],
        rp_dir="piccolo_testing",
        verbose=True,
        very_verbose=True,
        debug_flag=False
    )

    try:
        print("\n-----------Running Piccolo Instrument----------- ")
        ############ LAUNCHING PICCOLO METHODS ON RED PITAYA ############
        launch_thread = threading.Thread(target=instrument.launch_piccolo_rp, daemon=True)

        launch_thread.start()
        print("\n[piccolo-instrument] Launching Piccolo RP server...")

        time.sleep(12)  # Give time for the server to start

        # Start cliend threads
        print("\n[piccolo-instrument] Piccolo server started.")
        
        
        ############ CONNECTING PICCOLO METHODS ON RED PITAYA TO PC ############
        # Start streaming clients
        instrument.start_clients()
        time.sleep(1)  # Give time for the clients to start

        print("\n[piccolo-instrument] Piccolo PC clients started.")
             
        
        ############ TESTING ADC STREAM CLIENT ############
        print("\n-----------Running Piccolo Tests----------- ")
        print("\n[Test] ADC Stream Client testing.")

        for _ in range(3):  # ~1 second if 0.1s stream interval
            time.sleep(0.1)
            if instrument.adc_stream_client.adc1_data is not None:
                print("[Test] Received ADC data block.")
                ch1 = instrument.adc_stream_client.adc1_data
                ch2 = instrument.adc_stream_client.adc2_data

                print(f"[Test] The length of ch1 list is {len(ch1)}")
                print(f"[Test] Ch1 Max: {np.max(ch1):.4f}, Ch2 Max: {np.max(ch2):.4f}")
            else:
                print("[Test] No data yet.")


            
    except KeyboardInterrupt:
        print("Interrupted by user.")
    except socket.error as sock_err:
        print(f"Socket error: {sock_err}")
    except Exception as local_err:
        print(f"Error: {local_err}")
    finally:
        instrument.stop_servers()
