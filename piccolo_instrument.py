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


###
# TODO:
# - enable the asynchronous transfer of the script to the red pitaya and running it compared to spinning up the clients.
#   do these really all need to be in the same class?? feels like they should be separate. it's hard for me to organize them in my mind
#   and see how they can be cleanly used together.
# - In general, the file transfer and running on the rp works cleanly. need to figure out the whole osc client / server thing.
# - 

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



    ################ Red Pitaya Setup and Run Methods ################

    def get_rp_login(self):
        """ Get the local information for the Red Pitaya and run the script on it"""
        
        # Load the Red Pitaya login information from a JSON file
        with open("redpitaya/rp_login_desk.json", "r") as f:
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
        """SSH into the Red Pitaya and get calibration values for the ADCs"""
        
        # Connect to the Red Pitaya and add directory if missing
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, username=self.username, password=self.password)
        ssh.exec_command(f"mkdir -p {self.rp_dir}")

        _, stdout, stderr = ssh.exec_command("/opt/redpitaya/bin/calib -rv")

        output = stdout.read().decode()
        errors = stderr.read().decode()

        ssh.close()

        if errors:
            print("Errors:", errors)
            return None

        calib_data = {}
        for line in output.strip().splitlines():
            match = re.match(r"(\w+)\s*=\s*(-?\d+)", line.strip())
            if match:
                key, value = match.groups()
                calib_data[key] = int(value)
                
        calibration_values = {}

        for channel in range(1,3):
            gain_key = f"FE_CH{channel}_FS_G_LO"
            offset_key = f"FE_CH{channel}_DC_offs"
            gain = calib_data[gain_key] 
            offset = calib_data[offset_key]
            calibration_values[f"CH{channel}"] = [gain, offset]

        self.calibration_values = calibration_values

        # Debug
        if self.verbose:
            print("\nRed Pitaya calibration values loaded successfully")
        if self.very_verbose:
            print("Calibration data:", calib_data)
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
            data_callback=self._on_adc_data)
        self.memory_stream_client = MemoryStreamClient(
            data_callback=self._on_memory_data)
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


    def stop_servers(self):
        """Send kill command to Red Pitaya."""
        self.control_command_client.start(self.ip)
        time.sleep(1)  # Give time for kill to be sent
        self.control_command_client.stop()
        print("[Instrument] Red pitaya methods shut down successfully.")

    
    ################ Red Pitaya ADC Data Handling Methods ################

    def _on_adc_data(self, adc1_data, adc2_data):
        self.adc1_data = adc1_data
        self.adc2_data = adc2_data

        return self.adc1_data, self.adc2_data

    def _on_memory_data(self, fpgaoutput):
        if not fpgaoutput:
            return

        try:
            row = {}

            # Scalar metadata
            for key in ("droplet_id", "cur_time_us", "droplet_classification"):
                row[key] = fpgaoutput[key]
            
            for ch in (0, 1):
                ch_key = f"CH{ch+1}"
                _, offset = self.calibration_values[ch_key]

                # Intensity
                raw_int = fpgaoutput[f"cur_droplet_intensity[{ch}]"]
                row[f"cur_droplet_intensity[{ch}]"] = raw_int
                row[f"cur_droplet_intensity_v[{ch}]"] = (raw_int - offset) / 8192.0

                # Area
                raw_area = fpgaoutput[f"cur_droplet_area[{ch}]"]
                row[f"cur_droplet_area[{ch}]"] = raw_area
                row[f"cur_droplet_area_vms[{ch}]"] = raw_area / 8192.0 / 1000.0

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

    def save_log(self, filename="droplet_log.csv"):
        self.droplet_data.to_csv(filename, index=False)
        return None
    
    
    def set_gate_limits(self, sort_keys, limits):
        if self.verbose:
            print(f"[Instrument] Recieved gate limits to set: {limits}")

        sort_gates = {}

        for i, key in enumerate(sort_keys):
            # Parse channel index
            ch = int(key[key.find('[')+1:key.find(']')])
            ch_key = f"CH{ch+1}"
            _, offset = self.calibration_values[ch_key]

            # Select x/y based on index
            low_coord = 'x0' if i == 0 else 'y0'
            high_coord = 'x1' if i == 0 else 'y1'
            low_val = limits[low_coord][0]
            high_val = limits[high_coord][0]

            # Unit conversion
            def convert(val, key):
                if "_vms" in key:
                    return val * 8192.0 * 1000
                elif "_ms" in key:
                    return val * 1000
                elif "_v" in key:
                    return val * 8192.0 + offset
                else:
                    return val

            low_converted = int(convert(low_val, key))
            high_converted = int(convert(high_val, key))

            # Determine parameter type
            if "intensity" in key:
                param = "intensity"
            elif "width" in key:
                param = "width"
            elif "area" in key:
                param = "area"
            else:
                raise ValueError(f"Unrecognized key: {key}")

            sort_gates[f"low_{param}_thresh[{ch}]"] = low_converted
            sort_gates[f"high_{param}_thresh[{ch}]"] = high_converted

        if self.verbose:
            print(f"[Instrument] Setting sort gates: {sort_gates}")
        # Write sort_gates to FPGA memory
        for var, val in sort_gates.items():
            self.set_memory_variable(var, val)

        # Save for inspection
        self.sort_gates = sort_gates
        
        return self.sort_gates
    

if __name__ == "__main__":
    instrument = Instrument(
        local_script="piccolo_rp.py",
        local_dir="redpitaya",
        script_args=["--verbose", "--very_verbose"],
        rp_dir="piccolo_testing0430",
        verbose=True,
        very_verbose=True,
        debug_flag=True
    )

    try:
        print("\n-----------Running Piccolo Instrument-----------")
        ############ LAUNCHING PICCOLO METHODS ON RED PITAYA ############
        launch_thread = threading.Thread(target=instrument.launch_piccolo_rp, daemon=True)

        launch_thread.start()
        print("\n[piccolo-instrument] Launching Piccolo RP server...")

        time.sleep(9)  # Give time for the server to start

        # Start cliend threads
        print("\n[piccolo-instrument] Piccolo server started.")
        
        
        ############ CONNECTING PICCOLO METHODS ON RED PITAYA TO PC ############
        # Start streaming clients
        instrument.start_clients()
        time.sleep(1)  # Give time for the clients to start

        print("\n[piccolo-instrument] Piccolo PC clients started.")
             
        
        ############ TESTING ADC STREAM CLIENT ############
        print("\n-----------Running Piccolo Tests-----------")
        print("\n[Test] ADC Stream Client testing.")

        for _ in range(1):  # ~1 second if 0.1s stream interval
            time.sleep(0.1)
            if instrument.adc_stream_client.adc1_data is not None:
                print("[Test] Received ADC data block.")
                ch1 = instrument.adc_stream_client.adc1_data
                ch2 = instrument.adc_stream_client.adc2_data

                print(f"[Test] The length of ch1 list is {len(ch1)}")
                print(f"[Test] Ch1 Max: {np.max(ch1):.4f}, Ch2 Max: {np.max(ch2):.4f}")
            else:
                print("[Test] No data yet.")


        ############ TESTING MEM STREAM CLIENT ############
        print("\n[Test] Memory Stream Client testing.")

        # Read the droplet data buffer
        print(f"[Test] Droplet data buffer length: {len(instrument.droplet_data)}")
        print(instrument.droplet_data.head(30))
        instrument.save_log("droplet_log_0512.csv")

        
        ############ TESTING MEMORY COMMAND CLIENT ############
        print("\n[Test] Memory Command Client testing.")

        var_name = "low_intensity_thresh[0]"
        var_value = 1234
        
        try:
            # Read initial value
            fpgaoutput = instrument.memory_stream_client.fpgaoutput
            print(f"[Test] Initial Memory Value for {var_name}: {fpgaoutput[var_name]}")
            
            # Send a test variable update
            instrument.set_memory_variable(var_name, var_value)
            print("[Test] Set {var_value} to {var_value}")
            time.sleep(0.5)  # Give time for the command to be sent

            # Read updated value
            fpgaoutput = instrument.memory_stream_client.fpgaoutput
            print(f"[Test] Updated Memory Value for {var_name}: {fpgaoutput[var_name]}")

        finally:
            print("[Test] Memory Command Client stopped.")
            instrument.stop_clients()

        time.sleep(1)  # Give time for the clients to stop


        ############ TESTING DROPLET DATA BUFFER ############

            
    except KeyboardInterrupt:
        print("Interrupted by user.")
    except socket.error as sock_err:
        print(f"Socket error: {sock_err}")
    except Exception as local_err:
        print(f"Error: {local_err}")
    # finally:
    #     instrument.stop_servers()
