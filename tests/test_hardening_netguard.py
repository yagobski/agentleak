# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Outbound guard: DNS rebinding and proxy bypass (hardening review).

Everything here talks to a server on 127.0.0.1 that the test starts. Name
resolution is stubbed, so no request leaves the machine.
"""

from __future__ import annotations

import http.server
import socket
import subprocess
import sys
import textwrap
import threading
import urllib.request
from collections.abc import Iterator

import pytest

from agentleak.core.netguard import UnsafeURLError, open_model_url, set_outbound_guard

PUBLIC_ANSWER = "8.8.8.8"  # only ever returned by the stub, never connected to


class _Hits(http.server.BaseHTTPRequestHandler):
    hits: list[str] = []

    def do_GET(self) -> None:  # noqa: N802
        type(self).hits.append(self.path)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"internal": true}')

    do_POST = do_GET  # noqa: N815

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture()
def local_server() -> Iterator[int]:
    _Hits.hits = []
    srv = http.server.HTTPServer(("127.0.0.1", 0), _Hits)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield srv.server_address[1]
    finally:
        srv.shutdown()


def test_dns_rebinding_between_check_and_connect_is_refused(monkeypatch, local_server) -> None:
    """First answer public (passes the check), second answer loopback (the connect)."""
    real = socket.getaddrinfo
    calls = {"n": 0}

    def _rebinding(host, port, *args, **kwargs):  # noqa: ANN001, ANN202
        if host != "rebind.test":
            return real(host, port, *args, **kwargs)
        calls["n"] += 1
        ip = PUBLIC_ANSWER if calls["n"] == 1 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port or 0))]

    monkeypatch.setattr(socket, "getaddrinfo", _rebinding)
    set_outbound_guard(True)
    req = urllib.request.Request(f"http://rebind.test:{local_server}/v1/chat/completions")
    with pytest.raises(UnsafeURLError):
        open_model_url(req, timeout=5)
    assert _Hits.hits == []


def test_guard_off_still_reaches_a_local_model(local_server) -> None:
    set_outbound_guard(False)
    req = urllib.request.Request(f"http://127.0.0.1:{local_server}/v1/models")
    with open_model_url(req, timeout=5) as resp:
        assert resp.status == 200


def test_proxy_environment_does_not_carry_a_guarded_request(tmp_path, local_server) -> None:
    """With HTTP_PROXY set, urllib used to hand the request to the proxy, which
    resolves and connects on its own: the address check proved nothing."""
    script = tmp_path / "probe.py"
    script.write_text(textwrap.dedent(f"""
        import socket, urllib.request
        real = socket.getaddrinfo
        calls = {{"n": 0}}
        def fake(host, port, *a, **k):
            if host != "public.test":
                return real(host, port, *a, **k)
            calls["n"] += 1
            ip = "{PUBLIC_ANSWER}" if calls["n"] == 1 else "127.0.0.1"
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port or 0))]
        socket.getaddrinfo = fake
        from agentleak.core.netguard import open_model_url, set_outbound_guard
        set_outbound_guard(True)
        try:
            open_model_url(urllib.request.Request("http://public.test:1/x"), timeout=5)
            print("REACHED")
        except Exception as exc:
            print("REFUSED", type(exc).__name__)
    """))
    env = {"PATH": "/usr/bin:/bin", "HTTP_PROXY": f"http://127.0.0.1:{local_server}",
           "http_proxy": f"http://127.0.0.1:{local_server}", "NO_PROXY": ""}
    out = subprocess.run([sys.executable, "-I", str(script)], capture_output=True, text=True,
                         env=env, timeout=60, cwd=str(tmp_path))
    assert "REFUSED" in out.stdout, (out.stdout, out.stderr[-500:])
    assert _Hits.hits == []
