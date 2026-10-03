"""Generate real Pygame frames for visual review, independent of a projector."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pygame
from main import Application, ROOT
from src.game import Phase
from src.scenario_loader import load_scenario


def capture():
    output = ROOT / "docs" / "screenshots"
    output.mkdir(parents=True, exist_ok=True)
    app = Application(load_scenario(ROOT / "data/scenarios.json"), windowed=True)
    g = app.game
    scenes = [
        ("01-setup", Phase.SETUP), ("02-title", Phase.TITLE), ("03-brief", Phase.INTRO),
        ("04-story", Phase.SCENE), ("05-dialogue-vote", Phase.VOTE),
        ("06-vote-reveal", Phase.VOTE_REVEAL), ("07-tie", Phase.TIE),
        ("08-branch", Phase.BRANCH), ("09-analysis", Phase.ANALYSIS),
        ("10-analysis-reveal", Phase.ANALYSIS_REVEAL), ("11-transition", Phase.TRANSITION),
        ("12-final", Phase.FINAL), ("13-end", Phase.END),
    ]
    for name, phase in scenes:
        g.enter(phase)
        g.path = "A"
        g.votes = {0: "A", 1: "A", 2: "C", 3: "B"}
        g.answers = {0: "A", 1: "B"} if phase == Phase.VOTE else {0: "1", 1: "2"}
        g.selected_team = 2 if phase in (Phase.VOTE, Phase.ANALYSIS) else None
        if phase == Phase.TIE:
            g.votes = {0: "A", 1: "A", 2: "C", 3: "C"}
            g.path = None
        if phase in (Phase.ANALYSIS_REVEAL, Phase.FINAL):
            g.scores = [5, 3, 4, 3] if phase == Phase.FINAL else [1, 0, 1, 0]
            g.awards = [1, 0, 1, 0]
        app.phase_time = 10
        app.time = 8
        pygame.image.save(app.renderer.draw(app), output / (name + ".png"))
    # All narrative branches and answer layouts are rendered to prove no exceptions.
    for index in range(4):
        g.round_index = index
        for path in "ABC":
            g.path = path
            for phase in (Phase.BRANCH, Phase.ANALYSIS, Phase.ANALYSIS_REVEAL):
                g.enter(phase)
                app.phase_time = 10
                app.renderer.draw(app)
    pygame.quit()
    print(f"13 captures Pygame : {output}")


if __name__ == "__main__":
    capture()
