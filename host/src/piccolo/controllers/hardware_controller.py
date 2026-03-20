"""
HardwareController — controls real Piccolo hardware.

Manages Red Pitaya connection (SSH/SCP), TCP clients for data streaming,
and Cobalt Skyra laser box via serial.
"""

import os
import json
import paramiko
from scp import SCPClient
import threading
import numpy as np
import time
import posixpath
import pandas as pd

from piccolo.controllers.controller import InstrumentController
from piccolo.conversion import raw_to_volts
from piccolo.piccolo_clients import (
    ADCStreamClient,
    MemoryStreamClient,
    MemoryCommandClient,
    ControlCommandClient
)
from piccolo.drivers.laser import LaserBox


class HardwareController(InstrumentController):
    def __init__(self,
                 local_script="piccolo_rp.py",
                 local_dir="firmware/arm",
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
        self._load_rp_login()

        # Get calibration values
        self._load_calibration()

        # Setup laser
        self.laser_box = self._setup_laser()

        # Setup clients
        self._setup_clients()

        # Setup droplet data buffer
        self.data_lock = threading.Lock()
        self.buffer_size = 1000
        self._droplet_rows = []  # Fast append buffer
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
            "detection_channel": 0,
            "camera_trig_delay": 100,
            "camera_trig_duration": 50,
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

    ################ Red Pitaya Setup ################

    def _load_rp_login(self):
        """Load Red Pitaya login credentials from JSON."""
        with open("config/rp_login_4CH.json", "r") as f:
            rp_login_json = json.load(f)

        self.ip = rp_login_json["ip"]
        self.username = rp_login_json["username"]
        self.password = rp_login_json["password"]

        if self.verbose:
            print("\nRed Pitaya login information loaded successfully")
        if self.very_verbose:
            print(f"IP: {self.ip}")
            print(f"Username: {self.username}")
            print(f"Password: {self.password}")

    def _load_calibration(self):
        """Load ADC calibration values."""
        self.calibration_values = {
            "CH1": [-10, 1.0],
            "CH2": [-10, 1.0],
            "CH3": [-10, 1.0],
            "CH4": [-10, 1.0],
        }
        if self.verbose:
            print("\nRed Pitaya calibration values loaded successfully")

    def launch_piccolo_rp(self):
        """Deploy code to the Red Pitaya and launch the server process."""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, username=self.username, password=self.password)
        ssh.exec_command(f"mkdir -p {self.rp_dir}")

        if self.verbose:
            print("\nConnected to Red Pitaya successfully")

        # Transfer local directory to the Red Pitaya
        with SCPClient(ssh.get_transport()) as scp:
            for root, _, files in os.walk(self.local_dir):
                for file in files:
                    local_path = os.path.join(root, file)
                    remote_path = posixpath.join(self.rp_dir, file)
                    scp.put(local_path, remote_path)
                    if self.very_verbose:
                        print(f"Local file {local_path} transferred to Red Pitaya {remote_path}")

            # Also transfer the shared mmap config
            mmap_path = os.path.join("config", "piccolo_mmap.json")
            if os.path.exists(mmap_path):
                scp.put(mmap_path, posixpath.join(self.rp_dir, "piccolo_mmap.json"))
                if self.very_verbose:
                    print(f"Transferred {mmap_path} to Red Pitaya")

        if self.verbose:
            print(f"\nFiles transferred to Red Pitaya.")

        # Load the bitstream onto the FPGA
        bitstream_path = "/root/piccolo.bit.bin"
        load_cmd = f"sudo cat {bitstream_path} > /dev/xdevcfg"
        _, stdout, stderr = ssh.exec_command(load_cmd)
        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            if self.verbose:
                print(f"Successfully loaded bitstream from {bitstream_path}")
        else:
            print(f"ERROR: Failed to load bitstream. Exit code: {exit_status}. Stderr: {stderr.read().decode()}")

        if not self.debug_flag:
            args = " ".join(self.script_args)
            cmd = (
                f'cd {self.rp_dir} && '
                f'nohup sudo python3 {self.local_script} {args} '
                f'> piccolo_stdout.log 2> piccolo_stderr.log < /dev/null &'
            )
            ssh.exec_command(f'bash -c "{cmd}"')
            if self.verbose:
                print("\nScript launched in background. Use log files to monitor.")
        else:
            args = " ".join(self.script_args)
            cmd = f'bash -l -c "cd {self.rp_dir} && sudo python3 {self.local_script} {args}"'
            _, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
            try:
                for line in iter(stdout.readline, ""):
                    line = line.strip()
                    if line:
                        self.rp_output.append(line)
                        if self.very_verbose:
                            print(f"[RP stdout] {line}")
            except Exception as e:
                print(f"[Paramiko stdout read error] {e}")
            _ = stdout.channel.recv_exit_status()
            self.stdout = stdout.read().decode().strip()
            self.stderr = stderr.read().decode().strip()
            if self.verbose:
                print("\nScript executed. SSH channel closed.")

        ssh.close()

    def _setup_laser(self):
        """Initialize the laser box."""
        try:
            with open("config/laser_config.json", "r") as f:
                config = json.load(f)

            name2num_and_max_power_mw = {
                name: (details["num"], details["max_power_mw"])
                for name, details in config["lasers"].items()
            }

            laser_box = LaserBox(
                which_port=config["port"],
                serial_number=config["serial_number"],
                name2num_and_max_power_mw=name2num_and_max_power_mw,
                verbose=self.verbose
            )
            for name in laser_box.names:
                laser_box.set_power(name, 0)
                laser_box.set_active_state(name, False)
                laser_box.set_on_state(name, False)

            print("[HardwareController] LaserBox initialized successfully.")
            return laser_box
        except FileNotFoundError:
            print("[HardwareController] laser_config.json not found. Laser control disabled.")
        except Exception as e:
            print(f"[HardwareController] Failed to initialize LaserBox: {e}")
        return None

    ################ Client Methods ################

    def _setup_clients(self):
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
        print("[HardwareController] All clients started.")

    def stop_clients(self):
        """Stop all clients."""
        self.adc_stream_client.stop()
        self.memory_stream_client.stop()
        self.memory_command_client.stop()
        print("[HardwareController] All clients stopped.")

    ################ Abstract Method Implementations ################

    def set_memory_variable(self, variable, value):
        """Set FPGA memory variable via TCP client."""
        self.memory_command_client.send_set_command(variable, value)
        print(f"[HardwareController] Queued memory variable set: {variable} = {value}")
        self.fpga_registers[variable] = value

    def set_laser_on_state(self, name, state):
        """Set the on/off state of a laser, with a low power default."""
        print(f"[HardwareController] Setting laser '{name}' on state to {state}.")
        if self.laser_box:
            if state:
                self.laser_box.set_on_state(name, True)
                self.laser_box.set_active_state(name, True)
                self.laser_box.set_power(name, 4)  # 4mW
            else:
                self.laser_box.set_power(name, 0)
                self.laser_box.set_active_state(name, False)
                self.laser_box.set_on_state(name, False)

    def set_laser_power(self, name, power_mw):
        """Set the power of a laser."""
        if self.laser_box:
            self.laser_box.set_power(name, power_mw)

    def start(self):
        """Start clients (call launch_piccolo_rp separately if needed)."""
        self.start_clients()

    def stop(self):
        """Stop all clients and the remote server process."""
        print("[HardwareController] Initiating shutdown...")
        self.stop_clients()
        self._stop_servers()
        if self.laser_box:
            self.laser_box.shutdown()
            self.laser_box.close()
        print("[HardwareController] Shutdown complete.")

    def _stop_servers(self):
        """Send kill command to Red Pitaya."""
        self.control_command_client.start(self.ip)
        time.sleep(1)
        self.control_command_client.stop()
        print("[HardwareController] Red pitaya methods shut down successfully.")

    ################ ADC Data Handling ################

    def _get_adc_data(self, adc1_data, adc2_data, adc3_data, adc4_data):
        self.adc1_data = adc1_data
        self.adc2_data = adc2_data
        self.adc3_data = adc3_data
        self.adc4_data = adc4_data

    def _get_memory_data(self, fpgaoutput):
        if not fpgaoutput:
            return

        if self.very_verbose:
            print(f"[HardwareController] Received memory data: {fpgaoutput}")

        try:
            row = fpgaoutput
            for ch in range(4):
                raw_int = fpgaoutput[f"cur_droplet_intensity[{ch}]"]
                row[f"cur_droplet_intensity[{ch}]"] = raw_int
                row[f"cur_droplet_intensity_v[{ch}]"] = self.convert_raw_to_volts(raw_int, ch)

                raw_area = fpgaoutput[f"cur_droplet_area[{ch}]"]
                row[f"cur_droplet_area[{ch}]"] = raw_area
                row[f"cur_droplet_area_vms[{ch}]"] = self.convert_raw_to_volts(raw_area, ch) / 1000.0

                raw_width = fpgaoutput[f"cur_droplet_width[{ch}]"]
                row[f"cur_droplet_width[{ch}]"] = raw_width
                row[f"cur_droplet_width_ms[{ch}]"] = raw_width / 1000.0

            with self.data_lock:
                self.fpga_registers.update(fpgaoutput)
                self._droplet_rows.append(row)
                if len(self._droplet_rows) > self.buffer_size:
                    self._droplet_rows = self._droplet_rows[-self.buffer_size:]

        except Exception as e:
            print(f"[HardwareController] Error parsing droplet data: {e}")

    @property
    def droplet_data(self):
        """Build DataFrame from row buffer on read (called by UI at ~4Hz)."""
        with self.data_lock:
            rows = self._droplet_rows
        if not rows:
            return self._empty_droplet_df
        return pd.DataFrame(rows)

    @droplet_data.setter
    def droplet_data(self, value):
        """Allow direct assignment (used by clear_droplet_data)."""
        if isinstance(value, pd.DataFrame) and value.empty:
            with self.data_lock:
                self._droplet_rows = []
        self._empty_droplet_df = value
