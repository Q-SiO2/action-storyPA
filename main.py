"""Palo Alto presenter. Run with python main.py; no server needed in manual mode."""
import argparse
import logging
import os
from pathlib import Path
from queue import Empty
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

from src.game import Game, Phase, COLORS, DEFAULT_NAMES
from src.network import PresenterNetwork
from src.renderer import Renderer, SIZE
from src.scenario_loader import load_scenario, ScenarioError
from src.ui_components import font
from src.audio import Audio
from src.feedback import Feedback

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
EXTERNAL = Path(sys.executable).parent if getattr(sys, "frozen", False) else ROOT


class Application:
    def __init__(self, scenario, *, windowed=False, server_url="", error=None, muted=False, reduced_motion=False):
        pygame.display.init()
        pygame.font.init()
        font.cache_clear()
        pygame.display.set_caption("Palo Alto — Les signaux faibles")
        pygame.display.set_allow_screensaver(False)
        self.fullscreen = not windowed
        self.display = pygame.display.set_mode((0, 0) if self.fullscreen else (1280, 720),
                                               pygame.FULLSCREEN if self.fullscreen else pygame.RESIZABLE)
        self.renderer = Renderer()
        self.game = Game(scenario)
        self.audio = Audio(ROOT, muted=muted)
        self.feedback = Feedback(self.game, self.audio)
        self.reduced_motion = reduced_motion
        self.error = error
        self.server_url = server_url
        self.network = None
        self.connected = []
        self.setup_index = 0
        self.setup_fresh = True
        self.time = 0.0
        self.phase_time = 0.0
        self.timer = None
        self.paused = False
        self.help = False
        self.hud = False
        self.menu = None
        self.running = True
        self.last_revision = self.game.revision
        self.last_phase = self.game.phase

    @property
    def motion_time(self):
        return 0 if self.reduced_motion else self.time

    @property
    def visual_phase_time(self):
        return 1000 if self.reduced_motion else self.phase_time

    def start_network(self, fresh=False):
        if self.game.phase not in (Phase.TITLE, Phase.TRANSITION):
            self.game.notice = "Test réseau disponible à l'accueil et entre les manches."
            return
        if self.network and fresh:
            self.network.stop()
            self.network = None
        if self.network is None:
            try:
                self.network = PresenterNetwork(self.server_url or "http://127.0.0.1:8000")
            except ValueError as exc:
                self.game.notice = str(exc)
                self.game.mode = "MANUAL"
                return
        self.game.mode = "ONLINE"
        self.game.revision += 1
        self.network.publish(self.game.snapshot())
        self.network.start(self.game.names, COLORS)

    def toggle_display(self):
        self.fullscreen = not self.fullscreen
        self.display = pygame.display.set_mode(
            (0, 0) if self.fullscreen else (1280, 720),
            pygame.FULLSCREEN if self.fullscreen else pygame.RESIZABLE)

    def skip_or_advance(self):
        g = self.game
        if g.phase in (Phase.SCENE, Phase.BRANCH):
            duration = len(g.lines[g.line_index]["text"]) / g.scenario["timing"]["characters_per_second"]
        elif g.phase in (Phase.VOTE_REVEAL, Phase.ANALYSIS_REVEAL, Phase.FINAL):
            duration = 1.1
        else:
            duration = 0
        if not self.reduced_motion and self.phase_time < duration:
            self.phase_time = duration + 0.1
            return
        g.advance()

    def key(self, event):
        g, key = self.game, event.key
        if key == pygame.K_F11:
            self.toggle_display()
            return
        if key == pygame.K_F1:
            self.help = not self.help
            return
        if self.help:
            if key == pygame.K_ESCAPE:
                self.help = False
            return
        if self.menu:
            if key == pygame.K_ESCAPE:
                self.menu = None
            elif self.menu == "recovery":
                action = {pygame.K_r: "phase", pygame.K_c: "round", pygame.K_g: "game"}.get(key)
                if action:
                    self.menu = action
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.menu == "exit":
                    self.running = False
                elif self.menu == "phase":
                    g.restart_phase()
                elif self.menu == "round":
                    g.restart_round()
                elif self.menu == "game":
                    if self.network:
                        self.network.stop()
                        self.network = None
                    self.game = Game(g.scenario)
                    self.connected = []
                    self.setup_index = 0
                    self.setup_fresh = True
                    self.last_revision = -1
                self.menu = None
            return
        if key == pygame.K_ESCAPE:
            self.menu = "exit"
            return
        if self.error:
            return
        if g.phase == Phase.SETUP:
            if key in (pygame.K_TAB, pygame.K_DOWN, pygame.K_UP):
                direction = -1 if key == pygame.K_UP or (event.mod & pygame.KMOD_SHIFT) else 1
                self.setup_index = (self.setup_index + direction) % 4
                self.setup_fresh = True
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.setup_index < 3:
                    self.setup_index += 1
                    self.setup_fresh = True
                else:
                    g.advance()
                    if self.server_url:
                        self.start_network()
            elif key == pygame.K_BACKSPACE:
                g.names[self.setup_index] = "" if self.setup_fresh else g.names[self.setup_index][:-1]
                self.setup_fresh = False
            elif event.unicode and event.unicode.isprintable():
                if self.setup_fresh:
                    g.names[self.setup_index] = ""
                    self.setup_fresh = False
                if len(g.names[self.setup_index]) < 24:
                    g.names[self.setup_index] += event.unicode
            return
        if key == pygame.K_F2:
            self.hud = not self.hud
        elif key == pygame.K_p:
            self.paused = not self.paused
        elif key == pygame.K_m:
            self.audio.toggle()
        elif key == pygame.K_F3:
            self.reduced_motion = not self.reduced_motion
        elif key == pygame.K_F4:
            if g.switch_mode() and g.mode == "ONLINE":
                self.start_network()
        elif key == pygame.K_n:
            # Explicit opt-in after restart: new room, same local story and score.
            self.start_network(fresh=bool(self.network and not self.network.socket_ok))
        elif key == pygame.K_r:
            self.menu = "recovery"
        elif self.paused:
            return
        elif key == pygame.K_t and g.phase in (Phase.VOTE, Phase.ANALYSIS):
            self.timer = None if self.timer is not None else g.scenario["timing"]["dialogue_seconds" if g.phase == Phase.VOTE else "analysis_seconds"]
        elif key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
            self.skip_or_advance()
        elif key == pygame.K_BACKSPACE:
            team = g.undo()
            if team is not None and self.network and g.mode == "ONLINE":
                self.network.reopen(team, g.phase_id)
        elif g.phase == Phase.TIE and key in (pygame.K_a, pygame.K_b, pygame.K_c):
            g.choose_tie(pygame.key.name(key).upper())
        elif g.phase in (Phase.VOTE, Phase.ANALYSIS):
            # During online input digits select a team only, for presenter reopen.
            digits = {pygame.K_1: 1, pygame.K_2: 2, pygame.K_3: 3, pygame.K_4: 4,
                      pygame.K_KP1: 1, pygame.K_KP2: 2, pygame.K_KP3: 3, pygame.K_KP4: 4}
            digit = digits.get(key)
            if g.mode == "ONLINE":
                if digit is not None:
                    g.selected_team = digit - 1
                if key == pygame.K_DELETE and g.selected_team is not None:
                    team = g.selected_team
                    g.reopen(team)
                    if self.network:
                        self.network.reopen(team, g.phase_id)
            elif g.phase == Phase.ANALYSIS and digit is not None:
                if g.selected_team is None:
                    g.selected_team = digit - 1
                else:
                    g.record(g.selected_team, str(digit))
            elif digit is not None:
                g.selected_team = digit - 1
            elif g.selected_team is not None and key in (pygame.K_a, pygame.K_b, pygame.K_c):
                g.record(g.selected_team, pygame.key.name(key).upper())

    def update(self, dt):
        g = self.game
        if self.network:
            while True:
                try:
                    msg = self.network.inbox.get_nowait()
                except Empty:
                    break
                if msg.get("type") == "snapshot":
                    self.connected = msg.get("connected", [])
                    if g.mode == "ONLINE" and msg.get("phase_id") == g.phase_id and g.phase in (Phase.VOTE, Phase.ANALYSIS):
                        remote = {int(team): answer for team, answer in msg.get("submissions", {}).items()}
                        # Reopen acknowledgements remove local locks too. A previously
                        # queued full snapshot must never keep a team permanently locked.
                        for team in list(g.answers):
                            if team not in remote:
                                g.reopen(team)
                        for team, answer in remote.items():
                            if g.answers.get(team) != answer:
                                g.record(team, answer, online=True)
                elif msg.get("type") == "closed":
                    if g.mode == "ONLINE":
                        g.switch_mode()
                elif msg.get("type") == "connection_error":
                    g.notice = "Connexion perdue : F4 pour continuer au clavier. N pour réessayer entre les manches."
        if g.revision != self.last_revision:
            self.phase_time = 0
            if g.phase != self.last_phase:
                self.timer = None
            self.last_revision = g.revision
            self.last_phase = g.phase
        if not (self.paused or self.help or self.menu):
            self.time += dt
            self.phase_time += dt
            if self.timer is not None:
                self.timer = max(0, self.timer - dt)
        if self.network and not self.error:
            self.network.publish(g.snapshot())
        self.feedback.update(self, dt)

    def draw(self):
        image = self.renderer.draw(self)
        width, height = self.display.get_size()
        scale = min(width / SIZE[0], height / SIZE[1])
        fitted = (int(SIZE[0] * scale), int(SIZE[1] * scale))
        self.display.fill((0, 0, 0))
        self.display.blit(pygame.transform.smoothscale(image, fitted), ((width - fitted[0]) // 2, (height - fitted[1]) // 2))
        pygame.display.flip()

    def run(self, max_frames=None):
        clock = pygame.time.Clock()
        frames = 0
        try:
            while self.running:
                dt = min(clock.tick(60) / 1000, 0.1)
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.menu = "exit"
                    elif event.type == pygame.KEYDOWN:
                        self.key(event)
                try:
                    self.update(dt)
                    self.draw()
                except Exception as exc:
                    logging.exception("Erreur de présentation")
                    self.error = "Erreur interne : " + str(exc)[:220] + ". Consultez presenter.log puis relancez."
                    self.game.phase = Phase.SETUP
                    self.draw()
                frames += 1
                if max_frames and frames >= max_frames:
                    break
        finally:
            if self.network:
                self.network.stop()
            self.audio.stop()
            pygame.quit()


def main():
    parser = argparse.ArgumentParser(description="Palo Alto — jeu narratif à quatre équipes")
    parser.add_argument("--windowed", action="store_true", help="Fenêtre de développement")
    parser.add_argument("--scenario", type=Path, help="Autre fichier JSON")
    parser.add_argument("--server", default=os.getenv("PALO_ALTO_SERVER_URL", ""), help="Backend HTTP(S)")
    parser.add_argument("--smoke-frames", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--mute", action="store_true", help="Démarrer sans son")
    parser.add_argument("--reduced-motion", action="store_true", help="Désactiver les animations")
    args = parser.parse_args()
    logging.basicConfig(filename=EXTERNAL / "presenter.log", level=logging.WARNING, encoding="utf-8")
    editable = EXTERNAL / "data" / "scenarios.json"
    path = args.scenario or (editable if editable.exists() else ROOT / "data" / "scenarios.json")
    error = None
    try:
        scenario = load_scenario(path)
    except ScenarioError as exc:
        error = str(exc)
        scenario = {"title": "Configuration", "rounds": [], "subtitle": ""}
    Application(scenario, windowed=args.windowed, server_url=args.server, error=error,
                muted=args.mute, reduced_motion=args.reduced_motion).run(args.smoke_frames)


if __name__ == "__main__":
    main()
