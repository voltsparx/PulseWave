from __future__ import annotations

import json
import socket
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import unquote

from ..core.state import Track


class LanStreamServer:
    def __init__(self, tracks_provider: Callable[[], list[Track]]) -> None:
        self._tracks_provider = tracks_provider
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._host = "0.0.0.0"
        self._port = 0

    @property
    def running(self) -> bool:
        return self._server is not None and self._thread is not None and self._thread.is_alive()

    def start(self, host: str, port: int) -> str:
        if self.running:
            raise RuntimeError("LAN stream server is already running")
        self._host = host
        handler = self._make_handler()
        self._server = ThreadingHTTPServer((host, int(port)), handler)
        self._port = int(self._server.server_address[1])
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True, name="pulsewave-11-lan-stream")
        self._thread.start()
        return self.playlist_url

    def stop(self) -> None:
        if self._server is None:
            return
        try:
            self._server.shutdown()
            self._server.server_close()
        finally:
            self._server = None
            self._thread = None

    @property
    def playlist_url(self) -> str:
        host = self._public_host()
        return f"http://{host}:{self._port}/playlist.m3u"

    def status(self) -> dict[str, object]:
        return {
            "running": self.running,
            "host": self._host,
            "port": self._port,
            "playlist_url": self.playlist_url if self.running else "",
        }

    def _public_host(self) -> str:
        if self._host not in {"0.0.0.0", "::"}:
            return self._host
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            sock.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _make_handler(self) -> type[BaseHTTPRequestHandler]:
        outer = self

        class _Handler(BaseHTTPRequestHandler):
            server_version = "PulseWave11LAN/1.0"

            def log_message(self, fmt: str, *args: object) -> None:
                return

            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/health":
                    self._send_json({"ok": True, **outer.status()})
                    return
                if self.path == "/playlist.m3u":
                    self._send_playlist()
                    return
                if self.path.startswith("/file/"):
                    self._send_file()
                    return
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")

            def _send_json(self, payload: dict[str, object]) -> None:
                body = json.dumps(payload, indent=2).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _tracks(self) -> list[Track]:
                return [t for t in outer._tracks_provider() if t.source == "local" and t.path is not None and Path(t.path).exists()]

            def _send_playlist(self) -> None:
                tracks = self._tracks()
                host = outer._public_host()
                lines = ["#EXTM3U"]
                for idx, track in enumerate(tracks):
                    lines.append(f"#EXTINF:{int(track.duration or 0)},{track.artist} - {track.title}")
                    lines.append(f"http://{host}:{outer._port}/file/{idx}")
                body = ("\n".join(lines) + "\n").encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "audio/x-mpegurl; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_file(self) -> None:
                tail = unquote(self.path[len("/file/") :]).strip("/")
                if not tail.isdigit():
                    self.send_error(HTTPStatus.BAD_REQUEST, "invalid file index")
                    return
                idx = int(tail)
                tracks = self._tracks()
                if idx < 0 or idx >= len(tracks):
                    self.send_error(HTTPStatus.NOT_FOUND, "file index out of range")
                    return
                path = Path(str(tracks[idx].path))
                if not path.exists() or not path.is_file():
                    self.send_error(HTTPStatus.NOT_FOUND, "file missing")
                    return
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(path.stat().st_size))
                self.end_headers()
                with path.open("rb") as handle:
                    while True:
                        chunk = handle.read(64 * 1024)
                        if not chunk:
                            break
                        self.wfile.write(chunk)

        return _Handler
