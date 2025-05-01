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
                 verbose=True,
                 very_verbose=True,
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
        
        self.calib_data = calib_data
        
        # Debug
        if self.verbose:
            print("\nRed Pitaya calibration values loaded successfully")
        if self.very_verbose:
            print("Calibration data:", calib_data)

        return None
    
    
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
        self.stream_clients = {
            "adc": ADCStreamClient(),
            "memory": MemoryStreamClient()
        }
        self.memory_command_client = MemoryCommandClient()
        self.control_client = ControlCommandClient()
        

    def start_clients(self):
        """Start all Red Pitaya clients."""
        for name, client in self.stream_clients.items():
            client.start(self.ip)
            print(f"[Instrument] {name} client started.")

        self.memory_command_client.start(self.ip)
        print("[Instrument] Memory command client started.")


    def stop_clients(self):
        """Stop all clients."""
        for client in self.stream_clients.values():
            client.stop()
        self.memory_command_client.stop()
        print("[Instrument] All clients stopped.")


    def set_memory_variable(self, variable, value):
        """Set FPGA memory variable."""
        self.memory_command_client.send_set_command(variable, value)
        print(f"[Instrument] Queued memory variable set: {variable} = {value}")


    def stop_servers(self):
        """Send kill command to Red Pitaya."""
        self.control_client.start(self.ip)
        time.sleep(1)  # Give time for kill to be sent
        self.control_client.stop()
        print("[Instrument] Red pitaya methods shut down successfully.")

    
    ################ Run Piccolo Instrument ################
    def run(self):
        print("\n-----------Running Piccolo Instrument-----------")
        ############ LAUNCHING PICCOLO ON RED PITAYA ############

        print("\n-----------Launching Red Pitaya Methods-----------")
        launch_thread = threading.Thread(target=instrument.launch_piccolo_rp, daemon=True)
        launch_thread.start()
        print("\nLaunching Piccolo RP server...")

        time.sleep(10)  # Give time for the server to start

        # Start cliend threads
        print("\n-----------Launching PC Methods-----------")
        # Start streaming clients
        instrument.start_clients()

        print("\n-----------Running Red Pitaya & PC Methods-----------")





if __name__ == "__main__":
    instrument = Instrument(
        local_script="piccolo_rp.py",
        local_dir="redpitaya",
        script_args=["--verbose", "--very_verbose"],
        rp_dir="piccolo_testing0430",
        verbose=False,
        very_verbose=False,
        debug_flag=False
    )

    try:
        print("\n-----------Running Piccolo Instrument-----------")
        ############ LAUNCHING PICCOLO METHODS ON RED PITAYA ############
        launch_thread = threading.Thread(target=instrument.launch_piccolo_rp, daemon=True)

        launch_thread.start()
        print("\n[piccolo-instrument] Launching Piccolo RP server...")

        time.sleep(10)  # Give time for the server to start

        # Start cliend threads
        print("\n[piccolo-instrument] Piccolo server started.")
        
        time.sleep(1)  # Give time for the server to start

        
        ############ CONNECTING PICCOLO METHODS ON RED PITAYA TO PC ############

        # Start streaming clients
        instrument.start_clients()

        time.sleep(1)  # Give time for the clients to start

        print("\n[piccolo-instrument] Piccolo PC clients started.")
        
        
        ############ TESTING ADC STREAM CLIENT ############
        print("\n[Test] ADC Stream Client testing.")

        for _ in range(10):  # ~1 second if 0.1s stream interval
            time.sleep(0.1)
            if instrument.stream_clients["adc"].latest_data:
                print("[Test] Received ADC data block.")
                ch1 = instrument.stream_clients["adc"].adc1_data
                ch2 = instrument.stream_clients["adc"].adc2_data

                print(f"Ch1 Mean: {np.mean(ch1):.4f}, Ch2 Mean: {np.mean(ch2):.4f}")
            else:
                print("[Test] No data yet.")


        ############ TESTING MEM STREAM CLIENT ############
        print("\n[Test] Memory Stream Client testing.")
        
        for _ in range(10):
            time.sleep(0.1)
            if instrument.stream_clients["memory"].latest_data:
                fpgaoutput = instrument.stream_clients["memory"].fpgaoutput
                print("[Test] Received Memory Data:", fpgaoutput)
            else:
                print("[Test] No memory data yet.")

        
        ############ TESTING MEMORY COMMAND CLIENT ############
        print("\n[Test] Memory Command Client testing.")

        var_name = "low_intensity_thresh[0]"
        var_value = 1234
        

        try:
            # Read initial value
            fpgaoutput = instrument.stream_clients["memory"].fpgaoutput
            print(f"[Test] Initial Memory Value for {var_name}: {fpgaoutput[var_name]}")
            
            # Send a test variable update
            instrument.set_memory_variable(var_name, var_value)
            print("[Test] Set {var_value} to {var_value}")
            time.sleep(0.5)  # Give time for the command to be sent

            # Read updated value
            fpgaoutput = instrument.stream_clients["memory"].fpgaoutput
            print(f"[Test] Updated Memory Value for {var_name}: {fpgaoutput[var_name]}")

        finally:
            print("[Test] Memory Command Client stopped.")
            instrument.stop_clients()

        time.sleep(1)  # Give time for the clients to stop

        
    except KeyboardInterrupt:
        print("Interrupted by user.")
    except socket.error as sock_err:
        print(f"Socket error: {sock_err}")
    except Exception as local_err:
        print(f"Error: {local_err}")
    finally:
        instrument.stop_servers()

