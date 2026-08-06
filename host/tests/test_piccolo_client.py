"""Tests for PiccoloClient REST methods using an httpx MockTransport (no live server).

The WebSocket streaming paths are validated in end-to-end integration runs against a
mock FastAPI server; these unit tests cover the REST command/snapshot surface.
"""

import json

import httpx

from piccolo.piccolo_client import PiccoloClient


def _client_with_mock(handler):
    """Build a PiccoloClient whose HTTP calls are served by `handler`."""
    c = PiccoloClient("127.0.0.1", port=8000)
    c._http = httpx.Client(transport=httpx.MockTransport(handler), base_url=c._base_url)
    return c


def test_wait_until_ready_true():
    def handler(request):
        assert request.url.path == "/health"
        return httpx.Response(200, json={"status": "ok"})

    c = _client_with_mock(handler)
    try:
        assert c.wait_until_ready(timeout=1.0, interval=0.01) is True
    finally:
        c.close()


def test_wait_until_ready_false_when_unavailable():
    def handler(request):
        return httpx.Response(503)

    c = _client_with_mock(handler)
    try:
        assert c.wait_until_ready(timeout=0.3, interval=0.05) is False
    finally:
        c.close()


def test_get_registers_returns_dict():
    def handler(request):
        assert request.url.path == "/registers"
        return httpx.Response(200, json={"droplet_counter": 5, "sort_enable": 1})

    c = _client_with_mock(handler)
    try:
        regs = c.get_registers()
        assert regs["droplet_counter"] == 5
        assert regs["sort_enable"] == 1
    finally:
        c.close()


def test_get_registers_returns_empty_on_error():
    def handler(request):
        raise httpx.ConnectError("no server")

    c = _client_with_mock(handler)
    try:
        assert c.get_registers() == {}
    finally:
        c.close()


def test_set_register_posts_value():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"ok": True})

    c = _client_with_mock(handler)
    try:
        c.set_register("min_width_thresh[0]", 1234)
        assert "min_width_thresh" in seen["path"]
        assert seen["body"] == {"value": 1234}
    finally:
        c.close()


def test_shutdown_swallows_connection_drop():
    def handler(request):
        # Server exits mid-request; a dropped connection must not raise.
        raise httpx.ReadError("connection closed by server")

    c = _client_with_mock(handler)
    try:
        c.shutdown()  # should not raise
    finally:
        c.close()
