"""Curate downloaded Kenney CC0 packs; generate a restrained radio voice effect.

Download URLs and original names are recorded in docs/AUDIO_MOTION.md.
Run with the two extracted packs under .audio-source/{voice,interface}.
The game ships only the resulting WAVs; no download or DSP at runtime.
"""
import os
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
from array import array
import math
from pathlib import Path
import wave
import pygame

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "select": "interface/Audio/select_001.ogg",
    "lock": "interface/Audio/confirmation_002.ogg",
    "reopen": "interface/Audio/back_001.ogg",
    "transition": "interface/Audio/maximize_001.ogg",
    "reveal": "interface/Audio/glass_001.ogg",
    "voice_ready": "voice/Female/ready.ogg",
    "voice_final_round": "voice/Female/final_round.ogg",
    "voice_complete": "voice/Female/mission_completed.ogg",
}


def prepare():
    pygame.mixer.init(frequency=44100, size=-16, channels=1)
    output = ROOT / "assets/audio"
    output.mkdir(parents=True, exist_ok=True)
    for name, source in FILES.items():
        pcm = array("h", pygame.mixer.Sound(ROOT / ".audio-source" / source).get_raw())
        if name.startswith("voice_"):
            # Mostly dry speech, with a quiet ring modulation and 55 ms radio echo.
            # A short envelope removes clicks without losing consonants.
            dry = pcm[:]
            delay = int(44100 * 0.055)
            previous = 0
            for i, sample in enumerate(dry):
                lowpass = previous * 0.32 + sample * 0.68
                previous = lowpass
                carrier = 0.90 + 0.10 * math.sin(i * math.tau * 82 / 44100)
                echo = dry[i - delay] * 0.08 if i >= delay else 0
                envelope = min(1, i / 220, (len(dry) - i) / 441)
                pcm[i] = int(max(-30000, min(30000, (lowpass * carrier + echo) * envelope)))
        peak = max((abs(v) for v in pcm), default=1) or 1
        pcm = array("h", (int(v * 22000 / peak) for v in pcm))
        with wave.open(str(output / (name + ".wav")), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(44100)
            wav.writeframes(pcm.tobytes())
    for pack in ("voice", "interface"):
        (output / ("KENNEY_" + pack.upper() + "_LICENSE.txt")).write_text(
            (ROOT / ".audio-source" / pack / "License.txt").read_text(encoding="utf-8-sig"), encoding="utf-8")
    pygame.mixer.quit()


if __name__ == "__main__":
    prepare()
