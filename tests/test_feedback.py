import os
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
from pathlib import Path
from types import SimpleNamespace
import wave
import pygame
from src.audio import Audio
from src.feedback import Feedback
from src.game import Game, Phase
from src.scenario_loader import load_scenario

ROOT = Path(__file__).resolve().parents[1]


class Recorder:
    def __init__(self): self.calls = []
    def play(self, cue): self.calls.append(cue)
    def stop_voice(self): pass
    def suspend(self, paused): pass


def setup():
    game = Game(load_scenario(ROOT / "data/scenarios.json"))
    game.enter(Phase.VOTE)
    audio = Recorder()
    feedback = Feedback(game, audio)
    app = SimpleNamespace(game=game, setup_index=0, paused=False, help=False, menu=None)
    return game, audio, feedback, app


def test_private_answers_have_identical_once_only_feedback():
    results = []
    for answer in "ABC":
        game, audio, feedback, app = setup()
        game.selected_team = 0
        feedback.update(app, 0)
        assert feedback.card_offset(0) == (0, 0)
        feedback.update(app, .2)
        assert feedback.card_offset(0)[1] < 0
        game.record(0, answer)
        feedback.update(app, 0)
        feedback.update(app, .1)
        feedback.update(app, .1)
        results.append(list(audio.calls))
        assert feedback.card_offset(0, reduced=True) == (0, 0)
        game.reopen(0)
        feedback.update(app, 0)
        assert audio.calls[-1] == "reopen"
    assert results == [["select", "lock"]] * 3


def test_transition_voice_and_motion_are_not_repeated_by_snapshots():
    game, audio, feedback, app = setup()
    game.enter(Phase.FINAL)
    feedback.update(app, 0)
    assert audio.calls == ["reveal", "voice_complete"]
    start = feedback.transition_at
    for _ in range(10):
        game.revision += 1
        feedback.update(app, .1)
    assert len(audio.calls) == 2
    assert feedback.transition_at == start
    app.paused = True
    before = feedback.clock
    feedback.update(app, 2)
    assert feedback.clock == before


def test_packaged_audio_is_short_valid_and_mute_stops_both_channels():
    audio = Audio(ROOT)
    assert audio.available
    for path in (ROOT / "assets/audio").glob("*.wav"):
        with wave.open(str(path)) as wav:
            assert wav.getnchannels() == 1 and wav.getsampwidth() == 2
            assert 0 < wav.getnframes() / wav.getframerate() < 4
    audio.play("voice_complete")
    audio.play("select")
    audio.toggle()
    assert audio.muted and not audio.fx.get_busy() and not audio.voice.get_busy()
    audio.play("voice_complete")
    assert not audio.voice.get_busy()
    audio.stop()


def test_audio_device_failure_is_optional(monkeypatch):
    pygame.mixer.quit()
    def fail(*args, **kwargs): raise pygame.error("no audio device")
    monkeypatch.setattr(pygame.mixer, "init", fail)
    audio = Audio(ROOT)
    assert not audio.available
    audio.play("voice_ready")
    audio.toggle()
    audio.stop()
