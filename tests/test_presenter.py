import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
import pygame
import pytest
from main import Application
from src.game import Phase
from src.scenario_loader import load_scenario


@pytest.fixture
def app():
    app = Application(load_scenario(Path(__file__).resolve().parents[1] / "data/scenarios.json"), windowed=True)
    yield app
    pygame.quit()


def press(app, key, unicode=""):
    app.key(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode, mod=0))
    app.update(0)


def test_actual_keyboard_full_game(app):
    for _ in range(4):
        press(app, pygame.K_RETURN)
    assert app.game.phase == Phase.TITLE
    press(app, pygame.K_SPACE)
    press(app, pygame.K_SPACE)
    for index in range(4):
        while app.game.phase == Phase.SCENE:
            app.phase_time = 0
            line = app.game.line_index
            press(app, pygame.K_SPACE)
            assert app.game.line_index == line
            press(app, pygame.K_SPACE)
        for digit in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
            press(app, digit)
            press(app, pygame.K_a)
        assert app.game.complete
        press(app, pygame.K_SPACE)
        app.phase_time = 5
        press(app, pygame.K_SPACE)
        while app.game.phase == Phase.BRANCH:
            app.phase_time = 5
            press(app, pygame.K_SPACE)
        correct_key = {1: pygame.K_1, 2: pygame.K_2, 3: pygame.K_3}[app.game.analysis["correct"]]
        for digit in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
            press(app, digit)
            press(app, correct_key)
        press(app, pygame.K_SPACE)
        app.phase_time = 5
        press(app, pygame.K_SPACE)
        if index < 3:
            press(app, pygame.K_SPACE)
    assert app.game.phase == Phase.FINAL
    assert app.game.scores == [5] * 4
    app.phase_time = 5
    press(app, pygame.K_SPACE)
    assert app.game.phase == Phase.END


def test_pause_timer_and_confirmation(app):
    app.game.enter(Phase.VOTE)
    press(app, pygame.K_t)
    timer = app.timer
    press(app, pygame.K_p)
    app.update(2)
    assert app.timer == timer
    press(app, pygame.K_1)
    assert not app.game.answers and app.game.selected_team is None
    press(app, pygame.K_p)
    press(app, pygame.K_1)
    press(app, pygame.K_b)
    press(app, pygame.K_BACKSPACE)
    assert not app.game.answers
    press(app, pygame.K_r)
    press(app, pygame.K_c)
    assert app.game.phase == Phase.VOTE
    press(app, pygame.K_RETURN)
    assert app.game.phase == Phase.SCENE
    press(app, pygame.K_ESCAPE)
    assert app.running
    press(app, pygame.K_ESCAPE)
    assert app.menu is None


def test_reopen_snapshot_removes_queued_lock(app):
    game = app.game
    game.mode = "ONLINE"
    game.enter(Phase.VOTE)
    fake = SimpleNamespace(inbox=Queue(), publish=lambda state: None)
    app.network = fake
    fake.inbox.put({"type": "snapshot", "phase_id": game.phase_id, "submissions": {"0": "A"}})
    app.update(0)
    assert game.answers == {0: "A"}
    fake.inbox.put({"type": "snapshot", "phase_id": game.phase_id, "submissions": {}})
    app.update(0)
    assert game.answers == {}
    fake.inbox.put({"type": "snapshot", "phase_id": game.phase_id, "submissions": {"0": "B"}})
    app.update(0)
    assert game.answers == {0: "B"}
    game.switch_mode()
    fake.inbox.put({"type": "snapshot", "phase_id": game.phase_id, "submissions": {"0": "C"}})
    app.update(0)
    assert game.answers == {0: "B"}
    app.network = None


def test_fullscreen_switch_and_scaled_frame(app):
    press(app, pygame.K_F11)
    assert app.fullscreen
    press(app, pygame.K_F11)
    assert not app.fullscreen
    app.game.enter(Phase.SCENE)
    app.phase_time = 9
    for size in [(1920, 1080), (1600, 900), (1366, 768)]:
        app.display = pygame.display.set_mode(size)
        app.draw()
        assert app.display.get_size() == size


def test_error_screen_draws_without_scenario(app):
    app.game.scenario = {"title": "Configuration", "rounds": []}
    app.error = "scenarios.json → rounds[0].choices : exactement A, B, C."
    app.draw()
