"""One in-memory room registry. Only the presenter can publish game state."""
import asyncio
from collections import deque
from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
import re
import secrets
import time

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

log = logging.getLogger("paloalto")
ROOT = Path(__file__).resolve().parent
app = FastAPI(title="Palo Alto — transport", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
PHASES = {"TITLE", "INTRO", "SCENE", "DIALOGUE_VOTE_OPEN", "DIALOGUE_RESULTS",
          "TIE_BREAK", "BRANCH_PLAYING", "ANALYSIS_OPEN", "ANALYSIS_RESULTS",
          "ROUND_TRANSITION", "FINAL_SCOREBOARD", "SESSION_COMPLETE"}
OPEN = {"DIALOGUE_VOTE_OPEN", "ANALYSIS_OPEN"}
TTL = 3 * 60 * 60


class SessionSpec(BaseModel):
    names: list[str] = Field(min_length=4, max_length=4)
    colors: list[str] = Field(min_length=4, max_length=4)
    pins: list[str] | None = None


class Claim(BaseModel):
    team: int = Field(ge=0, le=3)
    pin: str = Field(default="", max_length=12)
    reconnect_token: str = Field(default="", max_length=128)


@dataclass
class Room:
    code: str
    session_id: str
    token: str
    names: list[str]
    colors: list[str]
    pins: list[str] | None
    state: dict = field(default_factory=lambda: {
        "phase": "TITLE", "phase_id": "", "revision": -1, "round_id": 1,
        "mode": "ONLINE", "scores": [0] * 4, "awards": [0] * 4,
        "options": [], "question": "", "results": {}, "path": None})
    submissions: dict = field(default_factory=dict)
    tokens: dict = field(default_factory=dict)
    clients: dict = field(default_factory=dict)
    presenter: WebSocket | None = None
    updated: float = field(default_factory=time.monotonic)

    def snapshot(self, team=None, presenter=False):
        state = dict(self.state)
        # Claims, secrets and another team's unrevealed selection never leave their role.
        state["type"] = "snapshot"
        state["session_id"] = self.session_id
        state["room_code"] = self.code
        state["names"] = self.names
        state["colors"] = self.colors
        state["connected"] = list(self.clients)
        state["locked"] = list(self.submissions)
        if presenter:
            state["submissions"] = dict(self.submissions)
        elif team is not None:
            state["team"] = team
            state["own_answer"] = self.submissions.get(team)
            if state["phase"] != "FINAL_SCOREBOARD" and state["phase"] != "SESSION_COMPLETE":
                state["score"] = state.pop("scores")[team]
                state["award"] = state.pop("awards")[team]
                state["results"] = {str(team): state.get("results", {}).get(str(team))}
        return state


rooms: dict[str, Room] = {}
rates: dict[str, deque] = {}


def rate_limit(key, maximum=30):
    now = time.monotonic()
    if len(rates) > 5000:
        rates.clear()
    events = rates.setdefault(key, deque())
    while events and events[0] < now - 60:
        events.popleft()
    if len(events) >= maximum:
        raise HTTPException(429, "Trop de tentatives. Réessayez dans une minute.")
    events.append(now)


def get_room(code):
    if not re.fullmatch(r"[0-9]{4}", code) or code not in rooms:
        raise HTTPException(404, "Session inconnue ou terminée.")
    return rooms[code]


async def expire_rooms():
    """Bound memory use even if the presenter disappears without closing."""
    now = time.monotonic()
    for code, room in list(rooms.items()):
        if now - room.updated > TTL:
            await close_room(room)


@app.get("/health")
async def health():
    await expire_rooms()
    return {"status": "ok"}


@app.get("/")
@app.get("/join")
async def mobile():
    return FileResponse(ROOT / "static" / "index.html")


@app.post("/api/sessions")
async def create_session(spec: SessionSpec, request: Request):
    rate_limit("create:" + (request.client.host if request.client else "local"), 12)
    await expire_rooms()
    if len(rooms) >= 100:
        raise HTTPException(503, "Capacité temporairement atteinte.")
    names = [n.strip() for n in spec.names]
    if any(not n or len(n) > 24 or any(ord(c) < 32 for c in n) for n in names):
        raise HTTPException(422, "Quatre noms de 1 à 24 caractères sont requis.")
    if any(not re.fullmatch(r"#[0-9a-fA-F]{6}", c) for c in spec.colors):
        raise HTTPException(422, "Couleur hexadécimale invalide.")
    if spec.pins is not None and (len(spec.pins) != 4 or any(not re.fullmatch(r"[0-9]{4,8}", p) for p in spec.pins)):
        raise HTTPException(422, "Quatre PIN numériques de 4 à 8 chiffres sont requis.")
    code = str(secrets.randbelow(9000) + 1000)
    while code in rooms:
        code = str(secrets.randbelow(9000) + 1000)
    room = Room(code, secrets.token_hex(12), secrets.token_urlsafe(32), names, spec.colors, spec.pins)
    rooms[code] = room
    base = os.getenv("PUBLIC_URL", str(request.base_url).rstrip("/")).rstrip("/")
    log.info("SESSION CREATED %s", code)
    return {"room_code": code, "session_id": room.session_id,
            "presenter_token": room.token, "mobile_url": f"{base}/join?room={code}"}


@app.get("/api/rooms/{code}")
async def room_info(code: str):
    room = get_room(code)
    return {"names": room.names, "colors": room.colors, "requires_pin": room.pins is not None,
            "occupied": list(room.tokens)}


@app.post("/api/rooms/{code}/claim")
async def claim_team(code: str, claim: Claim, request: Request):
    rate_limit("claim:" + (request.client.host if request.client else "local"), 40)
    room = get_room(code)
    if claim.team in room.tokens:
        if not secrets.compare_digest(room.tokens[claim.team], claim.reconnect_token):
            raise HTTPException(409, "Cette équipe est déjà réservée à son contrôleur.")
    else:
        if room.pins and not secrets.compare_digest(room.pins[claim.team], claim.pin):
            raise HTTPException(403, "PIN incorrect.")
        room.tokens[claim.team] = secrets.token_urlsafe(32)
    room.updated = time.monotonic()
    return {"token": room.tokens[claim.team], "team": claim.team, "session_id": room.session_id}


async def send(socket, value):
    try:
        await asyncio.wait_for(socket.send_json(value), timeout=3)
    except (RuntimeError, WebSocketDisconnect, OSError, asyncio.TimeoutError):
        pass


async def broadcast(room):
    if room.presenter:
        await send(room.presenter, room.snapshot(presenter=True))
    for team, socket in list(room.clients.items()):
        await send(socket, room.snapshot(team=team))


async def close_room(room):
    rooms.pop(room.code, None)
    for socket in [room.presenter, *room.clients.values()]:
        if socket:
            await send(socket, {"type": "closed"})
            try:
                await socket.close(code=1000)
            except (RuntimeError, OSError):
                pass
    log.info("SESSION ENDED %s", room.code)


async def receive(socket, timeout=45, limit=16384):
    text = await asyncio.wait_for(socket.receive_text(), timeout)
    if len(text.encode("utf-8")) > limit:
        raise ValueError("Message trop volumineux.")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Objet JSON attendu.")
    return value


def validate_state(state):
    if not isinstance(state, dict) or state.get("phase") not in PHASES:
        raise ValueError("Phase invalide.")
    if type(state.get("round_id")) is not int or not 1 <= state["round_id"] <= 4:
        raise ValueError("Manche invalide.")
    if not isinstance(state.get("phase_id"), str) or not 1 <= len(state["phase_id"]) <= 80:
        raise ValueError("Identifiant de phase invalide.")
    if type(state.get("revision")) is not int or state["revision"] < 0:
        raise ValueError("Révision invalide.")
    if state.get("mode") not in ("MANUAL", "ONLINE"):
        raise ValueError("Mode invalide.")
    for field_name in ("scores", "awards"):
        values = state.get(field_name)
        if not isinstance(values, list) or len(values) != 4 or any(type(v) is not int or not 0 <= v <= 5 for v in values):
            raise ValueError("Scores invalides.")
    options = state.get("options")
    if not isinstance(options, list) or len(options) > 4:
        raise ValueError("Options invalides.")
    for option in options:
        if not isinstance(option, dict) or not isinstance(option.get("text"), str) or len(option["text"]) > 260:
            raise ValueError("Option invalide.")
    ids = [o.get("id") for o in options]
    if state["phase"] == "DIALOGUE_VOTE_OPEN" and ids != list("ABC"):
        raise ValueError("Trois choix A/B/C requis.")
    if state["phase"] == "ANALYSIS_OPEN" and ids not in ([str(i) for i in range(1, 4)], [str(i) for i in range(1, 5)]):
        raise ValueError("Trois ou quatre réponses requises.")
    # Accept only whitelisted public fields; never forward arbitrary presenter data.
    return {key: state.get(key) for key in (
        "phase", "phase_id", "round_id", "revision", "mode", "scores", "awards",
        "question", "options", "path", "results", "title")}


@app.websocket("/ws/presenter/{code}")
async def presenter_socket(socket: WebSocket, code: str):
    await socket.accept()
    room = None
    try:
        room = get_room(code)
        auth = await receive(socket, timeout=8)
        if not secrets.compare_digest(str(auth.get("token", "")), room.token):
            await socket.close(code=4403)
            return
        if room.presenter:
            await room.presenter.close(code=4001)
        room.presenter = socket
        await broadcast(room)
        while True:
            msg = await receive(socket)
            room.updated = time.monotonic()
            if msg.get("type") == "ping":
                await send(socket, {"type": "pong"})
            elif msg.get("type") == "end":
                await close_room(room)
                break
            elif msg.get("type") == "reopen":
                team = msg.get("team")
                if type(team) is int and 0 <= team < 4 and room.state["phase"] in OPEN and msg.get("phase_id") == room.state["phase_id"]:
                    room.submissions.pop(team, None)
                    await broadcast(room)
            elif msg.get("type") == "state":
                state = validate_state(msg)
                if state["revision"] < room.state["revision"]:
                    continue
                if state["phase_id"] != room.state["phase_id"]:
                    room.submissions = {}
                room.state = state
                log.info("ROUND CHANGED %s %s %s", code, state["round_id"], state["phase"])
                await broadcast(room)
    except (HTTPException, ValueError, asyncio.TimeoutError, WebSocketDisconnect, RuntimeError):
        try:
            await socket.close(code=4400)
        except RuntimeError:
            pass
    finally:
        if room and room.presenter is socket:
            room.presenter = None
            await broadcast(room)


@app.websocket("/ws/team/{code}/{team}")
async def team_socket(socket: WebSocket, code: str, team: int):
    await socket.accept()
    room = None
    try:
        room = get_room(code)
        auth = await receive(socket, timeout=8, limit=1024)
        if team not in range(4) or team not in room.tokens or not secrets.compare_digest(str(auth.get("token", "")), room.tokens[team]):
            await socket.close(code=4403)
            return
        if team in room.clients:
            await socket.close(code=4409)
            return
        room.clients[team] = socket
        log.info("TEAM CONNECTED %s %s", code, team + 1)
        await broadcast(room)
        recent = deque()
        while True:
            msg = await receive(socket, limit=1024)
            now = time.monotonic()
            while recent and recent[0] < now - 10:
                recent.popleft()
            recent.append(now)
            if len(recent) > 30:
                await send(socket, {"type": "error", "message": "Trop de messages."})
                continue
            room.updated = now
            if msg.get("type") == "ping":
                await send(socket, {"type": "pong"})
                continue
            state = room.state
            valid = (msg.get("type") == "submit" and room.presenter is not None
                     and state["mode"] == "ONLINE" and state["phase"] in OPEN
                     and msg.get("session_id") == room.session_id
                     and msg.get("round_id") == state["round_id"]
                     and msg.get("phase_id") == state["phase_id"]
                     and msg.get("answer") in [o["id"] for o in state["options"]])
            if not valid:
                await send(socket, {"type": "error", "message": "Phase fermée ou réponse périmée."})
            elif team in room.submissions:
                # Retry of the exact same packet is acknowledged without scoring twice.
                if room.submissions[team] == msg["answer"]:
                    await send(socket, room.snapshot(team=team))
                else:
                    await send(socket, {"type": "error", "message": "Réponse déjà verrouillée."})
            else:
                room.submissions[team] = msg["answer"]
                log.info("VOTE RECEIVED %s %s", code, team + 1)
                await broadcast(room)
                if len(room.submissions) == 4 and room.presenter:
                    await send(room.presenter, {"type": "ALL_TEAMS_LOCKED", "phase_id": state["phase_id"]})
    except (HTTPException, ValueError, asyncio.TimeoutError, WebSocketDisconnect, RuntimeError):
        try:
            await socket.close(code=4400)
        except RuntimeError:
            pass
    finally:
        if room and room.clients.get(team) is socket:
            room.clients.pop(team, None)
            log.info("TEAM DISCONNECTED %s %s", code, team + 1)
            await broadcast(room)


if __name__ == "__main__":
    import uvicorn
    # A single worker is required because rooms live in memory.
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")), ws_max_size=16384)
