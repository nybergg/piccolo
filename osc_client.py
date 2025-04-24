import socket
import struct
import matplotlib.pyplot as plt
import numpy as np
import time

# Server settings
# IP_ADDR = "10.11.23.84"
IP_ADDR = "10.11.21.163"
TCP_PORT = 5000
BUFFER_SIZE = 16384 * 4  # 16384 floats, each 4 bytes

def receive_data(client_socket, expected_bytes):
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

def main():
    # Connect to the server
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.settimeout(5)  # Set timeout to prevent hanging
    client_socket.connect((IP_ADDR, TCP_PORT))
    print("Connected to server.")

    # Send stream command
    message = struct.pack("I", 3).ljust(16, b'\x00')

    # Initialize Matplotlib interactive plot
    plt.ion()
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6))

    # Initialize plot lines
    x = np.arange(16384)  # X-axis sample indices
    y1 = np.zeros(16384)  # Channel 1 values
    y2 = np.zeros(16384)  # Channel 2 values

    ch1_line, = ax1.plot(x, y1, label='CH1')
    ch2_line, = ax2.plot(x, y2, label='CH2')

    ax1.set_ylim(-0.1, 1)
    ax2.set_ylim(-0.1, 1)
    ax1.legend()
    ax2.legend()

    print("Plot initialized.")

    try:
        while True:
            client_socket.sendall(message)
            print("Stream command sent.")

            # Receive data for both channels
            ch1_data = receive_data(client_socket, BUFFER_SIZE)
            ch2_data = receive_data(client_socket, BUFFER_SIZE)

            if ch1_data is None or ch2_data is None:
                print("Connection lost. Exiting.")
                break

            # Convert received binary data to float arrays
            ch1_data = np.array(struct.unpack(f'{16384}f', ch1_data))
            ch2_data = np.array(struct.unpack(f'{16384}f', ch2_data))

            # Smoothly update the plot without redrawing axes
            ch1_line.set_ydata(ch1_data)
            ch2_line.set_ydata(ch2_data)

            plt.pause(0.01)  # Small pause for UI update

    except KeyboardInterrupt:
        print("Interrupted by user.")

    finally:
        shutdown_msg = struct.pack("I", 99).ljust(16, b'\x00')
        client_socket.sendall(shutdown_msg)
        print("Shutdown command sent.")
        client_socket.close()
        print("Connection closed.")
        plt.ioff()
        plt.show()

if __name__ == "__main__":
    main()
