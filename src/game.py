"""Authoritative game state. No rendering or networking dependencies."""
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
import uuid

COLORS = ["#33E6FF", "#FF4FD8", "#5CFF85", "#FFC857"]
DEFAULT_NAMES = ["Équipe Cyan", "Équipe Magenta", "Équipe Verte", "Équipe Ambre"]


class Phase(str, Enum):
    SETUP = "SETUP"
    TITLE = "TITLE"
    INTRO = "INTRO"
    SCENE = "SCENE"
    VOTE = "DIALOGUE_VOTE_OPEN"
    VOTE_REVEAL = "DIALOGUE_RESULTS"
    TIE = "TIE_BREAK"
    BRANCH = "BRANCH_PLAYING"
    ANALYSIS = "ANALYSIS_OPEN"
    ANALYSIS_REVEAL = "ANALYSIS_RESULTS"
    TRANSITION = "ROUND_TRANSITION"
    FINAL = "FINAL_SCOREBOARD"
    END = "SESSION_COMPLETE"


@dataclass
class Game:
    scenario: dict
    names: list[str] = field(default_factory=lambda: DEFAULT_NAMES.copy())
    scores: list[int] = field(default_factory=lambda: [0] * 4)
    phase: Phase = Phase.SETUP
    round_index: int = 0
    line_index: int = 0
    selected_team: int | None = None
    answers: dict[int, str] = field(default_factory=dict)
    history: list = field(default_factory=list)
    path: str | None = None
    phase_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    revision: int = 0
    awards: list[int] = field(default_factory=lambda: [0] * 4)
    round_start_scores: list[int] = field(default_factory=lambda: [0] * 4)
    votes: dict[int, str] = field(default_factory=dict)
    mode: str = "MANUAL"
    notice: str = ""

    @property
    def node(self):
        return self.scenario["rounds"][self.round_index]

    @property
    def branch(self):
        return self.node["choices"][self.path or "A"]

    @property
    def analysis(self):
        return self.branch["analysis"]

    @property
    def lines(self):
        return self.branch["branch"] if self.phase == Phase.BRANCH else self.node["intro"]

    @property
    def complete(self):
        return len(self.answers) == 4

    @property
    def tally(self):
        return {key: Counter(self.votes.values())[key] for key in "ABC"}

    @property
    def tied(self):
        maximum = max(self.tally.values())
        return [key for key, value in self.tally.items() if value == maximum]

    def enter(self, phase: Phase):
        self.phase = phase
        self.phase_id = uuid.uuid4().hex
        self.revision += 1
        self.selected_team = None
        self.notice = ""
        if phase in (Phase.VOTE, Phase.ANALYSIS):
            self.answers = {}
            self.history = []
        if phase in (Phase.SCENE, Phase.BRANCH):
            self.line_index = 0

    def record(self, team: int, answer: str, *, online=False):
        if self.phase not in (Phase.VOTE, Phase.ANALYSIS) or not 0 <= team < 4:
            return False
        allowed = list("ABC") if self.phase == Phase.VOTE else [str(i + 1) for i in range(len(self.analysis["answers"]))]
        if answer not in allowed or (online and team in self.answers):
            return False
        self.history.append((team, self.answers.get(team)))
        self.answers[team] = answer
        self.selected_team = None
        self.notice = "Toutes les réponses sont reçues. ESPACE pour révéler." if self.complete else "Réponse enregistrée."
        return True

    def undo(self):
        if self.phase not in (Phase.VOTE, Phase.ANALYSIS) or not self.history:
            return None
        team, previous = self.history.pop()
        if previous is None:
            self.answers.pop(team, None)
        else:
            self.answers[team] = previous
        self.selected_team = team
        return team

    def reopen(self, team):
        if self.phase in (Phase.VOTE, Phase.ANALYSIS):
            self.answers.pop(team, None)
            self.history = [item for item in self.history if item[0] != team]
            self.selected_team = team

    def choose_tie(self, path):
        if self.phase == Phase.TIE and path in self.tied:
            self.path = path
            self.enter(Phase.BRANCH)

    def advance(self):
        if self.phase == Phase.SETUP:
            self.names = [name.strip() or DEFAULT_NAMES[i] for i, name in enumerate(self.names)]
            self.enter(Phase.TITLE)
        elif self.phase == Phase.TITLE:
            self.enter(Phase.INTRO)
        elif self.phase == Phase.INTRO:
            self.enter(Phase.SCENE)
        elif self.phase in (Phase.SCENE, Phase.BRANCH):
            if self.line_index + 1 < len(self.lines):
                self.line_index += 1
                self.revision += 1
            else:
                self.enter(Phase.VOTE if self.phase == Phase.SCENE else Phase.ANALYSIS)
        elif self.phase == Phase.VOTE and self.complete:
            self.votes = self.answers.copy()
            self.path = self.tied[0] if len(self.tied) == 1 else None
            self.enter(Phase.VOTE_REVEAL)
        elif self.phase == Phase.VOTE_REVEAL:
            self.enter(Phase.TIE if self.path is None else Phase.BRANCH)
        elif self.phase == Phase.ANALYSIS and self.complete:
            self.awards = [
                self.node["points"] if self.answers[i] == str(self.analysis["correct"]) else 0
                for i in range(4)
            ]
            self.scores = [score + award for score, award in zip(self.scores, self.awards)]
            self.enter(Phase.ANALYSIS_REVEAL)
        elif self.phase == Phase.ANALYSIS_REVEAL:
            self.enter(Phase.FINAL if self.round_index == 3 else Phase.TRANSITION)
        elif self.phase == Phase.TRANSITION:
            self.round_index += 1
            self.round_start_scores = self.scores.copy()
            self.path = None
            self.enter(Phase.SCENE)
        elif self.phase == Phase.FINAL:
            self.enter(Phase.END)

    def restart_round(self):
        self.scores = self.round_start_scores.copy()
        self.awards = [0] * 4
        self.path = None
        self.votes = {}
        self.answers = {}
        self.history = []
        self.enter(Phase.SCENE)

    def restart_phase(self):
        if self.phase == Phase.ANALYSIS_REVEAL:
            self.scores = [s - a for s, a in zip(self.scores, self.awards)]
            self.awards = [0] * 4
            self.enter(Phase.ANALYSIS)
        elif self.phase in (Phase.VOTE_REVEAL, Phase.TIE):
            self.path = None
            self.votes = {}
            self.enter(Phase.VOTE)
        else:
            self.enter(self.phase)

    def switch_mode(self):
        if self.mode == "ONLINE":
            self.mode = "MANUAL"
            # Fresh ownership fence: queued phone submissions must not enter manual input.
            self.phase_id = uuid.uuid4().hex
            self.revision += 1
            self.notice = "Mode manuel : les réponses reçues sont conservées."
            return True
        if self.phase in (Phase.TITLE, Phase.TRANSITION):
            self.mode = "ONLINE"
            self.phase_id = uuid.uuid4().hex
            self.revision += 1
            return True
        self.notice = "Retour en ligne possible à l'accueil ou entre deux manches."
        return False

    def snapshot(self):
        options = []
        question = ""
        if self.phase == Phase.VOTE:
            question = self.node["prompt"]
            options = [{"id": key, "text": item["text"]} for key, item in self.node["choices"].items()]
        elif self.phase == Phase.ANALYSIS:
            question = self.analysis["question"]
            options = [{"id": str(i + 1), "text": text} for i, text in enumerate(self.analysis["answers"])]
        return {
            "type": "state", "phase": self.phase.value, "phase_id": self.phase_id,
            "round_id": self.round_index + 1, "revision": self.revision, "mode": self.mode,
            "question": question, "options": options, "scores": self.scores,
            "awards": self.awards if self.phase == Phase.ANALYSIS_REVEAL else [0] * 4,
            "path": self.path if self.phase not in (Phase.VOTE, Phase.SCENE) else None,
            "results": self.answers if self.phase == Phase.ANALYSIS_REVEAL else self.votes if self.phase in (Phase.VOTE_REVEAL, Phase.TIE, Phase.BRANCH) else {},
            "locked": list(self.answers) if self.phase in (Phase.VOTE, Phase.ANALYSIS) else [],
            "title": self.node["title"],
        }
