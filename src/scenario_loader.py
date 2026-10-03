"""Validate editable content before opening a presentation."""
import json
from pathlib import Path


class ScenarioError(ValueError):
    pass


def load_scenario(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ScenarioError(f"{path.name} : lecture impossible ({exc}).") from exc

    def require(ok, field, message):
        if not ok:
            raise ScenarioError(f"{path.name} → {field} : {message}")

    def string(value, field, maximum=260):
        require(isinstance(value, str) and 0 < len(value.strip()) <= maximum,
                field, f"texte requis (1–{maximum} caractères).")

    require(isinstance(data, dict), "racine", "objet JSON requis.")
    string(data.get("title"), "title", 70)
    string(data.get("subtitle"), "subtitle", 160)
    require(isinstance(data.get("characters"), dict), "characters", "objet requis.")
    for name, color in data["characters"].items():
        string(name, "characters.nom", 24)
        require(isinstance(color, str) and len(color) == 7 and color.startswith("#")
                and all(c in "0123456789abcdefABCDEF" for c in color[1:]),
                f"characters.{name}", "couleur hexadécimale #RRGGBB.")
    require(isinstance(data.get("axioms"), dict) and set(data["axioms"]) == set("12345"),
            "axioms", "les cinq axiomes (clés 1 à 5) sont requis.")
    for key, value in data["axioms"].items():
        string(value, f"axioms.{key}", 220)
    timing = data.get("timing")
    require(isinstance(timing, dict), "timing", "objet requis.")
    for key in ("dialogue_seconds", "analysis_seconds", "characters_per_second"):
        value = timing.get(key)
        require(type(value) in (int, float) and 1 <= value <= 150,
                f"timing.{key}", "nombre entre 1 et 150.")
    rounds = data.get("rounds")
    require(isinstance(rounds, list) and len(rounds) == 4, "rounds", "exactement quatre manches.")

    def lines(value, field):
        require(isinstance(value, list) and 1 <= len(value) <= 3, field, "1–3 lignes.")
        for i, line in enumerate(value):
            require(isinstance(line, dict), f"{field}[{i}]", "objet requis.")
            require(line.get("speaker") in data["characters"], f"{field}[{i}].speaker",
                    "personnage absent de characters.")
            string(line.get("text"), f"{field}[{i}].text", 220)

    coverage = set()
    for i, node in enumerate(rounds):
        prefix = f"rounds[{i}]"
        require(isinstance(node, dict), prefix, "objet requis.")
        require(node.get("id") == i + 1, prefix + ".id", "numérotation 1 à 4.")
        for key in ("title", "location", "skill", "prompt"):
            string(node.get(key), prefix + "." + key, 80)
        require(node.get("points") == (2 if i == 3 else 1), prefix + ".points", "barème 1, 1, 1, 2.")
        lines(node.get("intro"), prefix + ".intro")
        choices = node.get("choices")
        require(isinstance(choices, dict) and set(choices) == set("ABC"), prefix + ".choices",
                "exactement A, B, C.")
        for key, choice in choices.items():
            field = prefix + ".choices." + key
            require(isinstance(choice, dict), field, "objet requis.")
            string(choice.get("text"), field + ".text", 125)
            lines(choice.get("branch"), field + ".branch")
            analysis = choice.get("analysis")
            require(isinstance(analysis, dict), field + ".analysis", "objet requis.")
            for name in ("question", "explanation", "label"):
                string(analysis.get(name), field + ".analysis." + name)
            answers = analysis.get("answers")
            require(isinstance(answers, list) and 3 <= len(answers) <= 4,
                    field + ".analysis.answers", "trois ou quatre réponses.")
            for j, answer in enumerate(answers):
                string(answer, field + f".analysis.answers[{j}]", 150)
            require(type(analysis.get("correct")) is int and 1 <= analysis["correct"] <= len(answers),
                    field + ".analysis.correct", "indice de réponse à partir de 1.")
            ax = analysis.get("axioms")
            require(isinstance(ax, list) and ax and all(type(a) is int and 1 <= a <= 5 for a in ax),
                    field + ".analysis.axioms", "liste d'IDs 1–5.")
            coverage.update(ax)
    require(coverage == set(range(1, 6)), "rounds", "couvrir les cinq axiomes.")
    return data
