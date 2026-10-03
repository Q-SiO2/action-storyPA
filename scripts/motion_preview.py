"""Render a small animated proof from actual presenter frames."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
import pygame
from main import Application, ROOT
from src.game import Phase
from src.scenario_loader import load_scenario


def capture():
    app = Application(load_scenario(ROOT / "data/scenarios.json"), windowed=True, muted=True)
    game = app.game
    game.enter(Phase.VOTE)
    app.update(0)
    frames = []
    for frame in range(90):
        if frame == 15: game.selected_team = 0
        if frame == 30: game.record(0, "A")
        if frame == 45: game.reopen(0)
        if frame == 60: game.enter(Phase.ANALYSIS)
        app.update(1 / 30)
        surface = pygame.transform.smoothscale(app.renderer.draw(app), (960, 540))
        frames.append(Image.frombytes("RGB", surface.get_size(), pygame.image.tobytes(surface, "RGB")))
    path = ROOT / "docs/screenshots/22-motion-preview.gif"
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=33, loop=0, optimize=False)
    app.audio.stop()
    pygame.quit()
    print(path)


if __name__ == "__main__": capture()
