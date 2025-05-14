import socket
import struct
import threading
import time
import json
import numpy as np

def recv_data(sock, size):
    """Helper function to receive correct 'size' bytes."""
    data = b''
    while len(data) < size:
        packet = sock.recv(size - len(data))
        if not packet:
            return None
        data += packet
    return data


class BaseClient:
    """Base class for all Red Pitaya clients."""
    def __init__(self, port, is_streaming_client=True):
        self.port = port
        self.ip = None
        self.sock = None
        self.connected = False
        self.thread = None
        self.stop_flag = threading.Event()
        self.is_streaming_client = is_streaming_client

    def connect(self, ip):
        """Connect to the target IP and port."""
        self.ip = ip
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5)
        self.sock.connect((self.ip, self.port))
        self.connected = True
        print(f"[{self.__class__.__name__}] Connected to {self.ip}:{self.port}")

    def start(self, ip):
        """Start client behavior in a background thread."""
        self.connect(ip)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        """Signal thread to stop."""
        self.stop_flag.set()
        if self.thread:
            self.thread.join()
        self.close()

    def close(self):
        """Close socket."""
        if self.sock:
            self.sock.close()
            self.sock = None
            self.connected = False
            print(f"[{self.__class__.__name__}] Socket closed.")

    def _run(self):
        raise NotImplementedError("Subclass must implement _run()")
    

class ADCStreamClient(BaseClient):
    """Stream ADC waveform data."""
    def __init__(self, port=5001, data_callback=None):
        super().__init__(port, is_streaming_client=True)
        self.adc1_data = None
        self.adc2_data = None
        self.data_callback = data_callback
        self.lock = threading.Lock()

    def _run(self):
        n_channels = 2
        buffer_size = 4096 
        mem_size = 4
        packet_size = n_channels * buffer_size * mem_size # 2 channels, 16384 floats, each 4 bytes

        try:
            while not self.stop_flag.is_set():
                raw_data = recv_data(self.sock, packet_size)
                if not raw_data:
                    break
            
                float_data = struct.unpack(f'{n_channels*buffer_size}f', raw_data)
                with self.lock:
                    adc1_data = np.array(float_data[:buffer_size]) 
                    adc2_data = np.array(float_data[buffer_size:])
                    self.adc1_data = adc1_data
                    self.adc2_data = adc2_data
                if self.data_callback:
                    self.data_callback(adc1_data, adc2_data)

        except Exception as e:
            print(f"[ADCStreamClient] Error during _run: {e}")
        finally:
            self.close()

        return adc1_data, adc2_data

class MemoryStreamClient(BaseClient):
    """Stream droplet/memory data."""
    def __init__(self, port=5002, data_callback=None):
        super().__init__(port, is_streaming_client=True)
        self.fpgaoutput = None
        self.data_callback = data_callback
        self.lock = threading.Lock()

    def _run(self):
        packet_size = 16

        try:
            while not self.stop_flag.is_set():
                header = recv_data(self.sock, packet_size)
                if not header:
                    break
                json_len = struct.unpack("I", header[:4])[0]
                json_msg = recv_data(self.sock, json_len)
                if not json_msg:
                    break
                with self.lock:
                    fpgaoutput = json.loads(json_msg.decode())
                    self.fpgaoutput = fpgaoutput
                if self.data_callback:
                    self.data_callback(fpgaoutput)
        except Exception as e:
            print(f"[MemoryStreamClient] Error during _run: {e}")
        finally:
            self.close()

        return fpgaoutput


class MemoryCommandClient(BaseClient):
    """Send memory (variable/value) updates."""
    def __init__(self, port=5003):
        super().__init__(port, is_streaming_client=False)
        self.command_queue = []
        self.lock = threading.Lock()

    def send_set_command(self, variable, value):
        """Queue a memory set command (variable and value separately)."""
        with self.lock:
            self.command_queue.append((variable, value))

    def _run(self):
        try:
            while not self.stop_flag.is_set():
                with self.lock:
                    if self.command_queue:
                        variable, value = self.command_queue.pop(0)
                        message = json.dumps({"name": variable, "value": value}).encode()
                        header = struct.pack("I", len(message)).ljust(16, b'\x00')
                        self.sock.sendall(header + message)

                        print(f"[MemoryCommandClient] Sent: {variable} = {value}")
                time.sleep(0.1)
        except Exception as e:
            print(f"[MemoryCommandClient] Error during _run: {e}")
        finally:
            self.close()


class ControlCommandClient(BaseClient):
    """Send a one-time shutdown command for piccolo methods on the Red Pitaya."""
    def __init__(self, port=5000):
        super().__init__(port, is_streaming_client=False)

    def _run(self):
        kill_cmd = 99
        message = struct.pack("I", kill_cmd).ljust(16, b'\x00')

        try:
            print("[ControlCommandClient] Sending piccolo_rp shutdown command...")
            self.sock.sendall(message)
            print("[ControlCommandClient] Shutdown command sent successfully.")
        except Exception as e:
            print(f"[ControlCommandClient] Error sending shutdown command: {e}")
        finally:
            self.stop_flag.set()
            self.close()