"""Optional local audio: independent FX/voice channels, safe on silent machines."""
import logging
from pathlib import Path
import pygame


class Audio:
    def __init__(self, root: Path, muted=False):
        self.muted = muted
        self.available = False
        self.sounds = {}
        self.paused = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(8)
            self.fx = pygame.mixer.Channel(0)
            self.voice = pygame.mixer.Channel(1)
            for path in (root / "assets/audio").glob("*.wav"):
                sound = pygame.mixer.Sound(path)
                sound.set_volume(0.52 if path.stem.startswith("voice_") else 0.23)
                self.sounds[path.stem] = sound
            self.available = bool(self.sounds)
        except pygame.error as exc:
            logging.warning("Audio indisponible : %s", exc)

    def play(self, cue):
        if not self.available or self.muted or self.paused or cue not in self.sounds:
            return
        channel = self.voice if cue.startswith("voice_") else self.fx
        channel.play(self.sounds[cue])

    def stop_voice(self):
        if self.available:
            self.voice.stop()

    def toggle(self):
        self.muted = not self.muted
        if self.muted:
            self.stop()

    def suspend(self, paused):
        if not self.available or paused == self.paused:
            return
        self.paused = paused
        for channel in (self.fx, self.voice):
            channel.pause() if paused else channel.unpause()

    def stop(self):
        if self.available:
            self.fx.stop()
            self.voice.stop()
