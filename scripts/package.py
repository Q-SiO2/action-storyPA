"""Make the portable Windows ZIP with current docs, launchers and asset credits."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
NOTICE = """PALO ALTO — LES SIGNAUX FAIBLES

Extraire tout le ZIP puis ouvrir launch.bat (mode manuel sans Internet).
launch-online.bat utilise Railway : redémarrer le service avant la session.
Le backend est arrêté après les essais pour conserver les crédits.

Quatre noms puis ENTRÉE. ESPACE : continuer. F1 : aide. F11 : plein écran.
Vote : équipe 1–4 puis A/B/C. Analyse : équipe 1–4 puis réponse 1–4.
M : couper/activer le son. F3 : réduire les animations.
Les sons et les courtes annonces système en anglais sont inclus dans l'EXE.
Téléphones : SON / OFF par défaut, EFFETS / CALME disponible.
Vibration selon le navigateur et l'appareil.

Scénario modifiable : data/scenarios.json. Licences et détails : docs/AUDIO_MOTION.md.
Une répétition avec les enceintes, les téléphones et le projecteur est nécessaire.
"""


def package():
    (DIST / "LISEZMOI.txt").write_text(NOTICE, encoding="utf-8-sig")
    with ZipFile(DIST / "PaloAlto-Windows.zip", "w", ZIP_DEFLATED) as archive:
        for relative in ("PaloAlto.exe", "launch.bat", "launch-online.bat", "LISEZMOI.txt", "data/scenarios.json"):
            archive.write(DIST / relative, relative)
        archive.write(ROOT / "README.md", "README.md")
        for path in (ROOT / "docs").rglob("*"):
            if path.is_file(): archive.write(path, path.relative_to(ROOT))
        for path in (ROOT / "assets/audio").glob("*LICENSE.txt"):
            archive.write(path, path.relative_to(ROOT))
    print(DIST / "PaloAlto-Windows.zip")


if __name__ == "__main__": package()
