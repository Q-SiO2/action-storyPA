import json
from contextlib import ExitStack
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from backend.main import app, rooms, rates
from src.game import Game, Phase, COLORS, DEFAULT_NAMES
from src.scenario_loader import load_scenario
from pathlib import Path


@pytest.fixture
def client():
    rooms.clear()
    rates.clear()
    with TestClient(app) as client:
        yield client
    rooms.clear()


def create(client, **extra):
    response = client.post("/api/sessions", json={"names": DEFAULT_NAMES, "colors": COLORS, **extra})
    assert response.status_code == 200
    return response.json()


def until(socket, predicate):
    for _ in range(30):
        data = socket.receive_json()
        if predicate(data):
            return data
    pytest.fail("Expected socket event did not arrive")


def snapshot(socket, phase_id=None):
    return until(socket, lambda d: d["type"] == "snapshot" and (phase_id is None or d["phase_id"] == phase_id))


def test_session_invalid_and_close(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/join").status_code == 200
    assert client.get("/api/rooms/0000").status_code == 404
    session = create(client)
    code = session["room_code"]
    with client.websocket_connect("/ws/presenter/" + code) as presenter:
        presenter.send_json({"token": session["presenter_token"]})
        assert snapshot(presenter)["room_code"] == code
        presenter.send_json({"type": "end"})
        assert until(presenter, lambda d: d["type"] == "closed")
    assert client.get("/api/rooms/" + code).status_code == 404


def test_invalid_presenter_rejected(client):
    code = create(client)["room_code"]
    with client.websocket_connect("/ws/presenter/" + code) as socket:
        socket.send_json({"token": "wrong"})
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()


def test_claim_pin_occupied_and_reconnect(client):
    code = create(client, pins=["1234"] * 4)["room_code"]
    assert client.post(f"/api/rooms/{code}/claim", json={"team": 0}).status_code == 403
    token = client.post(f"/api/rooms/{code}/claim", json={"team": 0, "pin": "1234"}).json()["token"]
    assert client.post(f"/api/rooms/{code}/claim", json={"team": 0, "pin": "1234"}).status_code == 409
    assert client.post(f"/api/rooms/{code}/claim", json={"team": 0, "reconnect_token": token}).status_code == 200
    assert client.post(f"/api/rooms/{code}/claim", json={"team": 4}).status_code == 422
    with client.websocket_connect(f"/ws/team/{code}/0") as one:
        one.send_json({"token": token})
        snapshot(one)
        with client.websocket_connect(f"/ws/team/{code}/0") as two:
            two.send_json({"token": token})
            with pytest.raises(WebSocketDisconnect):
                two.receive_json()
    with client.websocket_connect(f"/ws/team/{code}/0") as reconnect:
        reconnect.send_json({"token": token})
        assert snapshot(reconnect)["team"] == 0


def test_four_clients_privacy_duplicates_stale_reopen_and_presenter_reconnect(client):
    session = create(client)
    code = session["room_code"]
    game = Game(load_scenario(Path(__file__).resolve().parents[1] / "data/scenarios.json"))
    game.mode = "ONLINE"
    game.enter(Phase.VOTE)
    with ExitStack() as stack:
        presenter = stack.enter_context(client.websocket_connect("/ws/presenter/" + code))
        presenter.send_json({"token": session["presenter_token"]})
        snapshot(presenter)
        presenter.send_json(game.snapshot())
        snapshot(presenter, game.phase_id)
        phones = []
        tokens = []
        for team in range(4):
            token = client.post(f"/api/rooms/{code}/claim", json={"team": team}).json()["token"]
            tokens.append(token)
            phone = stack.enter_context(client.websocket_connect(f"/ws/team/{code}/{team}"))
            phone.send_json({"token": token})
            snapshot(phone, game.phase_id)
            phones.append(phone)
        def submit(team, answer, phase_id=None):
            phones[team].send_json({"type": "submit", "answer": answer, "session_id": session["session_id"],
                                   "round_id": 1, "phase_id": phase_id or game.phase_id})
        for team, answer in enumerate("AACC"):
            submit(team, answer)
        complete = until(presenter, lambda d: d["type"] == "snapshot" and len(d["locked"]) == 4)
        assert complete["submissions"] == {"0": "A", "1": "A", "2": "C", "3": "C"}
        private = until(phones[0], lambda d: d["type"] == "snapshot" and len(d["locked"]) == 4)
        assert private["own_answer"] == "A"
        assert "submissions" not in private and "scores" not in private
        assert all(v is None for v in private["results"].values())
        submit(0, "A")
        assert snapshot(phones[0])["own_answer"] == "A"
        submit(0, "B")
        assert until(phones[0], lambda d: d["type"] == "error")
        submit(1, "A", "stale")
        assert until(phones[1], lambda d: d["type"] == "error")
        presenter.send_json({"type": "reopen", "team": 0, "phase_id": game.phase_id})
        assert until(phones[0], lambda d: d["type"] == "snapshot" and d["own_answer"] is None)
        submit(0, "B")
        assert until(presenter, lambda d: d["type"] == "snapshot" and d["submissions"].get("0") == "B")
        # Valid presenter token can reattach and obtains the authoritative response cache.
        replacement = stack.enter_context(client.websocket_connect("/ws/presenter/" + code))
        replacement.send_json({"token": session["presenter_token"]})
        assert snapshot(replacement)["submissions"]["0"] == "B"
        game.switch_mode()
        replacement.send_json(game.snapshot())
        snapshot(replacement, game.phase_id)
        submit(2, "A")
        assert until(phones[2], lambda d: d["type"] == "error")


def test_payload_validation_and_no_secret_leak(client):
    session = create(client)
    info = client.get("/api/rooms/" + session["room_code"]).json()
    assert "presenter_token" not in json.dumps(info)
    assert session["presenter_token"] not in json.dumps(info)
    assert client.post("/api/sessions", json={"names": ["x"] * 5, "colors": COLORS}).status_code == 422
