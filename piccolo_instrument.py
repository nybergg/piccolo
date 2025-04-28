import os
import json
import paramiko
from scp import SCPClient
import threading
import socket
import struct
import matplotlib.pyplot as plt
import numpy as np
import re


###
# TODO:
# - enable the asynchronous transfer of the script to the red pitaya and running it compared to spinning up the clients.
#   do these really all need to be in the same class?? feels like they should be separate. it's hard for me to organize them in my mind
#   and see how they can be cleanly used together.
# - In general, the file transfer and running on the rp works cleanly. need to figure out the whole osc client / server thing.
# - 

class Instrument:
    def __init__(self, 
                 local_script, 
                 script_args=None, 
                 rp_dir="piccolo_testing",
                 verbose=True,
                 very_verbose=True 
                 ):
        
        # Local and remote script information
        self.local_script = local_script
        self.local_dir = "redpitaya"
        self.script_args = script_args or []
        self.rp_dir = rp_dir

        # Verbosity levels
        self.verbose = verbose
        self.very_verbose = very_verbose

        # Get rp login information
        self.get_rp_login()

        # Get calibration values
        self.get_rp_calibration()
        

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
                    remote_path = os.path.join(self.rp_dir, file)
                    scp.put(local_path, remote_path)

        # Debug
        if self.verbose:
            print(f"\nPiccolo RP files transferred to {self.rp_dir} successfully")
            print(f"\nRunning {self.local_script} on Red Pitaya...")

        # Run the script on the Red Pitaya
        args = " ".join(self.script_args)
        script = os.path.basename(remote_path)
        cmd = f'bash -l -c "cd {self.rp_dir} && sudo python3 {script} {args}"'
        _, stdout, stderr = ssh.exec_command(cmd, get_pty=True)

        # Debug            
        if self.very_verbose:
            stdout_str = stdout.read().decode()
            print("\n///////////Output on Red Pitaya///////////")
            print(stdout_str)
            print("\n///////////End of Red Pitaya Output///////////")

        if self.verbose:
            print("\nScript executed successfully. Shell to Red Pitaya closed")
        
        # Close connection to Red Pitaya
        ssh.close()

        return stdout.read(), stderr.read()
    
    
    def get_rp_adc(self):
        
        # Connect to the server
        tcp_port = 5001
        
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(5)  # Set timeout to prevent hanging
        client_socket.connect((self.ip, tcp_port))
        print("Connected to server.")

        # Send stream command
        message = struct.pack("I", 3).ljust(16, b'\x00')

        try:
            while True:
                client_socket.sendall(message)
                print("Stream command sent.")

                # Receive data for both channels
                ch1_data = receive_data(client_socket)
                ch2_data = receive_data(client_socket)

                if ch1_data is None or ch2_data is None:
                    print("Connection lost. Exiting.")
                    break

                # Convert received binary data to float arrays
                self.ch1_data = np.array(struct.unpack(f'{16384}f', ch1_data))
                self.ch2_data = np.array(struct.unpack(f'{16384}f', ch2_data))

        except KeyboardInterrupt:
            print("Interrupted by user.")

        finally:
            client_socket.close()


        def receive_data(client_socket):
            expected_bytes = 16384 * 4  # 16384 floats, each 4 bytes

            """Receives a fixed amount of data from the socket."""
            data = b''
            while len(data) < expected_bytes:
                try:
                    packet = client_socket.recv(expected_bytes - len(data))
                    if not packet:
                        print("Connection closed by server.")
                        return None  # Connection closed
                    data += packet
                except socket.timeout:
                    print("Socket timeout, retrying...")
                    continue
                except Exception as e:
                    print(f"Receive error: {e}")
                    return None
            return data
    
        return None
        



    
if __name__ == "__main__":
    instrument = Instrument(local_script="redpitaya/piccolo_rp.py", script_args=["--verbose", "--very_verbose"], rp_dir="piccolo_testing0425", verbose=True, very_verbose=True)
    launch_thread   = threading.Thread(target=instrument.launch_piccolo_rp, daemon=True)
    # osc_thread      = threading.Thread(target=instrument.get_rp_adc, daemon=True)
    
    try:
        
        # Start the thread to deploy and run the script
        launch_thread.start()
        # Wait for the thread to finish
        # launch_thread.join()
        print("Launch thread in process...")
        
        # Start osc server thread
        input("Press Enter to start the osc server...")
        # osc_thread.start()
        # Wait for the osc thread to finish
        # osc_thread.join()
        # print("OSC thread finished.")
    except KeyboardInterrupt:
        print("Interrupted by user.")
    except socket.error as sock_err:
        print(f"Socket error: {sock_err}")
    except Exception as local_err:
        print(f"Error: {local_err}")

