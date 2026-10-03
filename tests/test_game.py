import copy
import json
from pathlib import Path
import pytest
from src.game import Game, Phase
from src.scenario_loader import load_scenario, ScenarioError

DATA = Path(__file__).resolve().parents[1] / "data/scenarios.json"


@pytest.fixture
def game():
    return Game(load_scenario(DATA))


@pytest.mark.parametrize("votes,winner", [
    ("AAAA", ["A"]), ("AAAB", ["A"]), ("AABC", ["A"]), ("AACC", ["A", "C"])
])
def test_distribution(game, votes, winner):
    game.enter(Phase.VOTE)
    for i, vote in enumerate(votes):
        game.record(i, vote)
    assert game.scores == [0] * 4
    game.advance()
    assert game.tied == winner
    assert game.phase == Phase.VOTE_REVEAL
    game.advance()
    if len(winner) > 1:
        assert game.phase == Phase.TIE
        game.choose_tie("B")
        assert game.phase == Phase.TIE
        game.choose_tie("C")
    assert game.phase == Phase.BRANCH


def test_undo_and_replacement(game):
    game.enter(Phase.VOTE)
    game.record(0, "A")
    game.record(0, "B")
    assert game.undo() == 0
    assert game.answers[0] == "A"
    game.undo()
    assert not game.answers
    assert not game.record(7, "A")
    assert not game.record(0, "D")


def test_four_rounds_and_scoring_once(game):
    game.advance()
    game.advance()
    game.advance()
    for index in range(4):
        while game.phase == Phase.SCENE:
            game.advance()
        assert game.phase == Phase.VOTE
        for i in range(4):
            game.record(i, "ABC"[index % 3])
        game.advance()
        game.advance()
        while game.phase == Phase.BRANCH:
            game.advance()
        for i in range(4):
            game.record(i, str(game.analysis["correct"]) if i != 3 else str(game.analysis["correct"] % 3 + 1))
        game.advance()
        before = game.scores.copy()
        game.advance()
        assert game.scores == before
        if index < 3:
            game.advance()
    assert game.phase == Phase.FINAL
    assert game.scores == [5, 5, 5, 0]
    game.advance()
    assert game.phase == Phase.END


def test_restart_rolls_back_only_current_round(game):
    game.round_index = 1
    game.scores = [2, 1, 1, 2]
    game.round_start_scores = [1, 1, 0, 1]
    game.restart_round()
    assert game.scores == [1, 1, 0, 1]
    assert game.phase == Phase.SCENE


def test_reopen_analysis_rolls_back_award(game):
    game.path = "A"
    game.enter(Phase.ANALYSIS)
    for i in range(4):
        game.record(i, "1")
    game.advance()
    assert game.scores == [1] * 4
    game.restart_phase()
    assert game.scores == [0] * 4
    assert game.phase == Phase.ANALYSIS
    assert not game.answers


def test_fallback_fences_late_messages_and_keeps_inputs(game):
    game.mode = "ONLINE"
    game.enter(Phase.VOTE)
    game.record(0, "A", online=True)
    old_id = game.phase_id
    assert game.switch_mode()
    assert game.phase_id != old_id
    assert game.answers == {0: "A"}
    assert game.mode == "MANUAL"
    assert not game.switch_mode()
    game.enter(Phase.TRANSITION)
    assert game.switch_mode()
    assert game.mode == "ONLINE"


@pytest.mark.parametrize("mutation,field", [
    (lambda d: d["rounds"].pop(), "rounds"),
    (lambda d: d["rounds"][0]["choices"].pop("C"), "choices"),
    (lambda d: d["rounds"][0]["choices"]["A"]["analysis"].update(correct=0), "correct"),
    (lambda d: d["rounds"][0]["intro"][0].update(speaker="Inconnu"), "speaker"),
    (lambda d: d["timing"].update(characters_per_second=0), "timing"),
])
def test_schema_reports_exact_field(tmp_path, mutation, field):
    data = copy.deepcopy(load_scenario(DATA))
    mutation(data)
    file = tmp_path / "scenarios.json"
    file.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ScenarioError, match=field):
        load_scenario(file)


def test_malformed_and_missing_json(tmp_path):
    file = tmp_path / "invalid.json"
    with pytest.raises(ScenarioError):
        load_scenario(file)
    file.write_text("{", encoding="utf-8")
    with pytest.raises(ScenarioError):
        load_scenario(file)
