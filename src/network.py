"""Background socket transport; Pygame never blocks on network I/O."""
import json
import os
from queue import Queue, Empty
import threading
import time
from urllib.parse import urlsplit

import httpx
import websocket


class PresenterNetwork:
    def __init__(self, server_url):
        self.url = server_url.rstrip("/")
        parsed = urlsplit(self.url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("PALO_ALTO_SERVER_URL doit être une URL HTTP(S).")
        if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1") and os.getenv("PALO_ALTO_ALLOW_LAN_HTTP") != "1":
            raise ValueError("Utilisez HTTPS, ou PALO_ALTO_ALLOW_LAN_HTTP=1 pour un réseau local de confiance.")
        self.ws_base = ("wss" if parsed.scheme == "https" else "ws") + "://" + parsed.netloc
        self.inbox = Queue()
        self.commands = Queue()
        self.latest = None
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.session = None
        self.status = "HORS LIGNE"
        self.health_ok = False
        self.socket_ok = False
        self.started = False
        self.thread = None

    def start(self, names, colors):
        if self.started:
            return
        self.started = True
        self.thread = threading.Thread(target=self._run, args=(names.copy(), colors.copy()), daemon=True)
        self.thread.start()

    def publish(self, state):
        with self.lock:
            self.latest = json.dumps(state, ensure_ascii=False)

    def reopen(self, team, phase_id):
        self.commands.put({"type": "reopen", "team": team, "phase_id": phase_id})

    def _run(self, names, colors):
        delay = 1
        while not self.stop_event.is_set():
            socket = None
            try:
                self.status = "RECONNEXION"
                if self.session is None:
                    with httpx.Client(timeout=5, trust_env=False) as client:
                        response = client.get(self.url + "/health")
                        response.raise_for_status()
                        self.health_ok = response.json().get("status") == "ok"
                        pins = os.getenv("PALO_ALTO_TEAM_PINS")
                        body = {"names": names, "colors": colors}
                        if pins:
                            body["pins"] = pins.split(",")
                        response = client.post(self.url + "/api/sessions", json=body)
                        response.raise_for_status()
                        self.session = response.json()
                socket = websocket.create_connection(
                    self.ws_base + "/ws/presenter/" + self.session["room_code"],
                    timeout=5, http_no_proxy=["localhost", "127.0.0.1"])
                socket.send(json.dumps({"type": "auth", "token": self.session["presenter_token"]}))
                socket.settimeout(0.2)
                sent = None
                ping_at = pong_at = time.monotonic()
                delay = 1
                while not self.stop_event.is_set():
                    with self.lock:
                        latest = self.latest
                    if latest is not None and latest != sent:
                        socket.send(latest)
                        sent = latest
                    while True:
                        try:
                            socket.send(json.dumps(self.commands.get_nowait()))
                        except Empty:
                            break
                    now = time.monotonic()
                    if now - ping_at >= 12:
                        socket.send('{"type":"ping"}')
                        ping_at = now
                    if now - pong_at > 40:
                        raise ConnectionError("Heartbeat expiré.")
                    try:
                        raw = socket.recv()
                        if not raw:
                            raise ConnectionError("Connexion fermée.")
                        msg = json.loads(raw)
                        pong_at = now
                        if msg.get("type") == "closed":
                            self.inbox.put(msg)
                            self.session = None
                            self.stop_event.set()
                            break
                        if msg.get("type") == "snapshot":
                            self.status = "EN LIGNE"
                            self.socket_ok = True
                            self.inbox.put(msg)
                    except websocket.WebSocketTimeoutException:
                        continue
            except Exception as exc:
                self.status = "RECONNEXION"
                self.socket_ok = False
                self.inbox.put({"type": "connection_error", "message": str(exc)[:150]})
                # A vanished room after a backend restart requires a fresh room/QR.
                # Manual mode keeps the story and scores; presenter opts in again.
                if isinstance(exc, websocket.WebSocketConnectionClosedException):
                    self.inbox.put({"type": "room_may_be_lost"})
            finally:
                if socket:
                    if self.stop_event.is_set():
                        try:
                            socket.send('{"type":"end"}')
                        except Exception:
                            pass
                    socket.close()
            self.stop_event.wait(delay)
            delay = min(delay * 2, 10)
        self.status = "HORS LIGNE"

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1.5)
