"""Tests for piccolo.piccolo_clients — protocol framing and recv_data helper."""

import struct
import threading

import pytest

from piccolo.piccolo_clients import recv_data, BaseClient


class TestRecvData:
    def test_receives_exact_bytes(self):
        """recv_data should accumulate chunks until size is reached."""
        # Simulate a socket that returns data in small chunks
        chunks = [b"hel", b"lo", b" ", b"world"]
        chunk_iter = iter(chunks)

        class FakeSocket:
            def recv(self, size):
                try:
                    return next(chunk_iter)
                except StopIteration:
                    return b""

        result = recv_data(FakeSocket(), 11)
        assert result == b"hello world"

    def test_returns_none_on_disconnect(self):
        """recv_data should return None if socket returns empty bytes."""
        class FakeSocket:
            def recv(self, size):
                return b""

        result = recv_data(FakeSocket(), 10)
        assert result is None

    def test_single_chunk(self):
        """recv_data should work when all data arrives at once."""
        data = b"complete_data_block"

        class FakeSocket:
            def recv(self, size):
                return data[:size]

        result = recv_data(FakeSocket(), len(data))
        assert result == data


class TestBaseClient:
    def test_init_defaults(self):
        client = BaseClient(port=5000)
        assert client.port == 5000
        assert client.connected is False
        assert client.sock is None

    def test_stop_flag_initially_clear(self):
        client = BaseClient(port=5000)
        assert not client.stop_flag.is_set()

    def test_close_without_connection(self):
        """Closing without a connection should not raise."""
        client = BaseClient(port=5000)
        client.close()
        assert client.connected is False


class TestClientServerIntegration:
    """Test BaseClient connect/disconnect with a real local socket."""

    def test_connect_and_close(self):
        import socket

        # Start a local TCP server
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))  # Bind to random available port
        port = server.getsockname()[1]
        server.listen(1)

        try:
            client = BaseClient(port=port)
            client.connect("127.0.0.1")
            assert client.connected is True

            # Accept on server side
            conn, _ = server.accept()
            conn.close()

            client.close()
            assert client.connected is False
        finally:
            server.close()
