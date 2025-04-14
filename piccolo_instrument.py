import os
import json
import paramiko
from scp import SCPClient
import threading
import socket
import struct
import matplotlib.pyplot as plt
import numpy as np


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
        self.script_args = script_args or []
        self.rp_dir = rp_dir
        self.verbose = verbose
        self.very_verbose = very_verbose
        self._get_rp_login()

    def deploy_and_run(self):
        self._connect()
        remote_script = self._transfer()
        output, errors = self._run_piccolo_rp(remote_script)
        self.ssh.close()
        return output, errors

    def _get_rp_login(self):
        # Debug
        if self.very_verbose:
            print("\nGetting Red Pitaya login information")

        with open("redpitaya/rp_login_vpn.json", "r") as f:
            rp_login_json = json.load(f)

        self.ip = rp_login_json["ip"]
        self.username = rp_login_json["username"]
        self.password = rp_login_json["password"]
        
        # Debug
        if self.very_verbose:
            print(f"IP: {self.ip}")
            print(f"Username: {self.username}")
            print(f"Password: {self.password}")

        if self.verbose:
            print("\nRed Pitaya login information retrieved successfully")  
        return None
        
    def _connect(self):
        # Debug
        if self.very_verbose:
            print("\nConnecting to Red Pitaya...")
        
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(self.ip, username=self.username, password=self.password)
        self.ssh.exec_command(f"mkdir -p {self.rp_dir}")
        
        # Debug
        if self.verbose:
            print("\nConnected to Red Pitaya successfully")
        return None

    def _transfer(self):
        if self.very_verbose:
            print("\nTransferring script to Red Pitaya...")
        
        remote_path = os.path.join(self.rp_dir, os.path.basename(self.local_script))
        with SCPClient(self.ssh.get_transport()) as scp:
            scp.put(self.local_script, remote_path)

        # Debug
        if self.verbose:
            print(f"\nScript transferred to {remote_path} successfully")

        return remote_path

    def _run_piccolo_rp(self, remote_path):
        # Debug
        if self.very_verbose:
            print("\nRunning script on Red Pitaya...")
        
        args = " ".join(self.script_args)
        script = os.path.basename(remote_path)
        cmd = f'bash -l -c "cd {self.rp_dir} && sudo python3 {script} {args}"'
        stdin, stdout, stderr = self.ssh.exec_command(cmd, get_pty=True)

        # Debug            
        if self.very_verbose:
            stdout_str = stdout.read().decode()
            print("\n///////////Output on Red Pitaya///////////")
            print(stdout_str)
            print("\n///////////End of Red Pitaya Output///////////")

        if self.verbose:
            print("\nScript executed successfully. Shell to Red Pitaya closed")
        return stdout.read(), stderr.read()
    
    def osc_stream(self):
        
        # Connect to the server
        tcp_port = 5000
        
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
    instrument = Instrument(local_script="redpitaya/piccolo_rp.py", script_args=["--verbose", "--very_verbose"], rp_dir="piccolo_testing0414", verbose=True, very_verbose=True)

    input("Press Enter to initiate the deploy and run thread on Red Pitaya...")
    # launch_thread = threading.Thread(target=instrument.deploy_and_run, daemon=True)
    osc_thread = threading.Thread(target=instrument.osc_stream, daemon=True)
    
    try:
        
        # # Start the thread to deploy and run the script
        # input("Press Enter to deploy and run the script on Red Pitaya...")
        # launch_thread.start()
        # # Wait for the thread to finish
        # launch_thread.join()
        # print("Launch thread finished.")
        
        # Start osc server thread
        input("Press Enter to start the osc server...")
        osc_thread.start()
        # Wait for the osc thread to finish
        osc_thread.join()
        print("OSC thread finished.")
    except KeyboardInterrupt:
        print("Interrupted by user.")
    except socket.error as sock_err:
        print(f"Socket error: {sock_err}")
    except Exception as local_err:
        print(f"Error: {local_err}")