"""Real WebSockets: the actual Pygame presenter + four phone transports."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
import pygame
import websockets
from main import Application, ROOT
from src.game import Phase
from src.scenario_loader import load_scenario


async def wait_for(app, predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.update(0.02)
        if predicate():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("Timed out awaiting presenter state")


async def snapshot(socket, predicate=lambda d: True):
    while True:
        msg = json.loads(await asyncio.wait_for(socket.recv(), 8))
        if msg.get("type") == "snapshot" and predicate(msg):
            return msg


async def simulate(url):
    app = Application(load_scenario(ROOT / "data/scenarios.json"), windowed=True, server_url=url)
    g = app.game
    phones = []
    tokens = []
    try:
        g.advance()
        app.start_network()
        await wait_for(app, lambda: app.network.socket_ok)
        session = app.network.session
        code = session["room_code"]
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            assert (await client.get(url + "/health")).json() == {"status": "ok"}
            assert "PALO ALTO" in (await client.get(url + "/join")).text
            for team in range(4):
                response = await client.post(f"{url}/api/rooms/{code}/claim", json={"team": team})
                response.raise_for_status()
                token = response.json()["token"]
                tokens.append(token)
                phone = await websockets.connect(app.network.ws_base + f"/ws/team/{code}/{team}")
                await phone.send(json.dumps({"token": token}))
                await snapshot(phone)
                phones.append(phone)
            await wait_for(app, lambda: len(app.connected) == 4)
            # Generate the lobby QR using the actual presenter renderer.
            app.phase_time = 10
            app.draw()
            output = ROOT / "docs/screenshots"
            output.mkdir(parents=True, exist_ok=True)
            pygame.image.save(app.renderer.surface, output / "14-network-lobby.png")
            g.advance()
            g.advance()
            expected = [0] * 4
            distributions = ["AAAA", "AAAB", "AABC", "AACC"]
            for index in range(4):
                while g.phase == Phase.SCENE:
                    g.advance()
                app.update(0.02)
                phase_id = g.phase_id
                for team, phone in enumerate(phones):
                    state = await snapshot(phone, lambda d: d["phase_id"] == phase_id)
                    assert "submissions" not in state and "scores" not in state
                    await phone.send(json.dumps({"type": "submit", "session_id": session["session_id"],
                        "round_id": index + 1, "phase_id": phase_id, "answer": distributions[index][team]}))
                await wait_for(app, lambda: g.complete)
                assert g.answers == dict(enumerate(distributions[index]))
                g.advance()
                g.advance()
                if g.phase == Phase.TIE:
                    g.choose_tie("C")
                while g.phase == Phase.BRANCH:
                    g.advance()
                app.update(0.02)
                phase_id = g.phase_id
                correct = str(g.analysis["correct"])
                for team, phone in enumerate(phones):
                    await snapshot(phone, lambda d: d["phase_id"] == phase_id)
                    answer = correct if team != 3 else str(int(correct) % 3 + 1)
                    await phone.send(json.dumps({"type": "submit", "session_id": session["session_id"],
                        "round_id": index + 1, "phase_id": phase_id, "answer": answer}))
                    if team != 3:
                        expected[team] += g.node["points"]
                await wait_for(app, lambda: g.complete)
                # Exercise an actual disconnect/reconnect after a locked analysis.
                if index == 1:
                    await phones[0].close()
                    await wait_for(app, lambda: 0 not in app.connected)
                    phone = await websockets.connect(app.network.ws_base + f"/ws/team/{code}/0")
                    await phone.send(json.dumps({"token": tokens[0]}))
                    restored = await snapshot(phone, lambda d: d["phase_id"] == phase_id)
                    assert restored["own_answer"] == correct
                    phones[0] = phone
                g.advance()
                app.update(0.02)
                assert g.scores == expected
                for phone in phones:
                    result = await snapshot(phone, lambda d: d["phase"] == "ANALYSIS_RESULTS")
                    assert result["score"] == expected[result["team"]]
                print(f"Round {index + 1}: votes={distributions[index]}, scores={g.scores}")
                g.advance()
                if index < 3:
                    g.advance()
            assert g.phase == Phase.FINAL and g.scores == [5, 5, 5, 0]
            app.update(0.02)
            for phone in phones:
                final = await snapshot(phone, lambda d: d["phase"] == "FINAL_SCOREBOARD")
                assert final["scores"] == g.scores
            g.advance()
            app.update(0.02)
            await asyncio.sleep(0.3)
            app.network.stop()
            for phone in phones:
                while True:
                    message = json.loads(await asyncio.wait_for(phone.recv(), 5))
                    if message["type"] == "closed":
                        break
            assert (await client.get(f"{url}/api/rooms/{code}")).status_code == 404
            print("PASS: health, mobile, QR, actual presenter + four clients, tie, reconnect, scores, closed room")
    finally:
        if app.network:
            app.network.stop()
        for phone in phones:
            await phone.close()
        pygame.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    asyncio.run(simulate(parser.parse_args().server.rstrip("/")))
