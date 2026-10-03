"""Semantic feedback: never reveal a private answer before the public reveal."""
import math
from .game import Phase


class Feedback:
    def __init__(self, game, audio):
        self.audio = audio
        self.phase_id = game.phase_id
        self.phase = game.phase
        self.answers = dict(game.answers)
        self.selected = game.selected_team
        self.setup_index = 0
        self.clock = 0.0
        self.events = {}
        self.transition_at = -10.0

    def update(self, app, dt):
        game = app.game
        blocked = app.paused or app.help or bool(app.menu)
        self.audio.suspend(blocked)
        if not blocked:
            self.clock += dt
        entered = game.phase_id != self.phase_id
        changed_teams = set()
        if entered:
            self.audio.stop_voice()
            if game.phase != self.phase:
                self.transition_at = self.clock
                cue = "reveal" if game.phase in (Phase.VOTE_REVEAL, Phase.ANALYSIS_REVEAL, Phase.FINAL) else "transition"
                if game.phase != Phase.SETUP:
                    self.audio.play(cue)
                voice = {Phase.TITLE: "voice_ready", Phase.FINAL: "voice_complete"}.get(game.phase)
                if game.phase == Phase.SCENE and game.round_index == 3:
                    voice = "voice_final_round"
                if voice:
                    self.audio.play(voice)
            self.answers = dict(game.answers)
            self.events.clear()
        else:
            # Lock feedback depends only on receipt, never correctness or A/B/C.
            locked = set(game.answers) - set(self.answers)
            reopened = set(self.answers) - set(game.answers)
            changed_teams = locked | reopened
            if locked:
                self.audio.play("lock")
            elif reopened:
                self.audio.play("reopen")
            for team in locked:
                self.events[team] = (self.clock, "lock")
            for team in reopened:
                self.events[team] = (self.clock, "reopen")
        selected = app.setup_index if game.phase == Phase.SETUP else game.selected_team
        previous = self.setup_index if self.phase == Phase.SETUP else self.selected
        if selected is not None and selected != previous and selected not in changed_teams:
            self.events[selected] = (self.clock, "select")
            self.audio.play("select")
        self.phase_id, self.phase = game.phase_id, game.phase
        self.answers = dict(game.answers)
        self.selected, self.setup_index = game.selected_team, app.setup_index

    def card_offset(self, team, reduced=False):
        if reduced or team not in self.events:
            return 0, 0
        start, kind = self.events[team]
        t = self.clock - start
        if not 0 <= t < 0.42:
            return 0, 0
        if kind == "reopen":
            return round(math.sin(t * 70) * 3 * (1 - t / 0.42)), 0
        return 0, -round(math.sin(t / 0.42 * math.pi) * (9 if kind == "select" else 5))
