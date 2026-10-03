"""Projector composition: generous hierarchy, terminal details, vector motion."""
import math
import pygame
import qrcode
from .game import Phase
from .ui_components import (
    BG, WHITE, GRAY, DIM, CYAN, MAGENTA, GREEN, AMBER, RED, TEAM_COLORS,
    text, paragraph, panel, signal, progress, glow_dot, font, wrapped,
)

SIZE = (1600, 900)


class Renderer:
    def __init__(self):
        self.surface = pygame.Surface(SIZE)
        self.qr_url = None
        self.qr = None
        self.backdrop = pygame.Surface(SIZE)
        self.backdrop.fill(BG)
        # Static atmosphere is cached; motion never competes with dialogue.
        for y in range(0, 900, 6):
            pygame.draw.line(self.backdrop, (7, 10, 14), (0, y), (1600, y))
        for x in range(80, 1600, 80):
            for y in range(80, 900, 80):
                pygame.draw.circle(self.backdrop, (21, 29, 38), (x, y), 1)
        self.backdrop = self.backdrop.convert()

    def draw(self, app):
        s = self.surface
        g = app.game
        s.blit(self.backdrop, (0, 0))
        pygame.draw.line(s, (33, 48, 61), (64, 99), (1536, 99))
        pygame.draw.rect(s, CYAN, (66, 36, 32, 32), 1, border_radius=5)
        pygame.draw.line(s, CYAN, (75, 59), (89, 44), 2)
        pygame.draw.lines(s, CYAN, False, [(78, 44), (89, 44), (89, 55)], 2)
        text(s, "PALO ALTO", (114, 31), 31, WHITE, bold=True)
        text(s, "/ COMMUNICATION SIMULATOR", (308, 42), 19, GRAY, mono=True)
        network = app.network
        online = g.mode == "ONLINE"
        status = network.status if network and online else "LOCAL"
        status_color = GREEN if status in ("EN LIGNE", "LOCAL") else AMBER
        glow_dot(s, (1188, 55), status_color, 4)
        text(s, f"{g.mode} // {status}", (1208, 43), 19, status_color, mono=True)
        if g.phase not in (Phase.SETUP, Phase.TITLE, Phase.INTRO, Phase.END):
            progress(s, g.round_index)
            text(s, f"SESSION_NODE / 0{g.round_index + 1}", (1326, 115), 18, GRAY, mono=True)
        if network and online and not network.socket_ok and g.phase != Phase.SETUP:
            text(s, "Connexion en attente : F4 pour jouer au clavier. N pour réessayer entre les manches.", (70, 171), 22, AMBER)
        elif g.notice and g.phase in (Phase.TITLE, Phase.TRANSITION):
            text(s, g.notice[:110], (70, 171), 22, AMBER)
        if app.error:
            self.error(app.error)
        elif g.phase == Phase.SETUP:
            self.setup(app)
        elif g.phase == Phase.TITLE:
            self.title(app)
        elif g.phase == Phase.INTRO:
            self.intro(app)
        elif g.phase in (Phase.SCENE, Phase.BRANCH):
            self.scene(app)
        elif g.phase in (Phase.VOTE, Phase.ANALYSIS):
            self.input(app)
        elif g.phase in (Phase.VOTE_REVEAL, Phase.TIE):
            self.vote_reveal(app)
        elif g.phase == Phase.ANALYSIS_REVEAL:
            self.analysis_reveal(app)
        elif g.phase == Phase.TRANSITION:
            self.transition(app)
        elif g.phase == Phase.FINAL:
            self.final(app)
        elif g.phase == Phase.END:
            self.end(app)
        self.teams(app)
        self.footer(app)
        if app.hud:
            panel(s, (1090, 175, 444, 129), GRAY, True)
            text(s, "HUD ANIMATEUR / ÉCRAN PUBLIC", (1110, 188), 19, AMBER, mono=True)
            text(s, g.phase.value, (1110, 226), 22, WHITE, mono=True)
            text(s, f"Manche {g.round_index + 1}/4 · {len(g.answers)}/4 reçues", (1110, 263), 22, GRAY)
        if app.help:
            self.help()
        if app.paused:
            panel(s, (618, 370, 364, 138), AMBER, True)
            text(s, "PAUSE", (697, 391), 48, AMBER, bold=True)
            text(s, "P pour reprendre", (678, 458), 24, WHITE)
        if app.menu:
            self.menu(app)
        # Short entrance fade. Skipping via SPACE sets phase_time above this interval.
        if app.phase_time < 0.20 and not app.menu:
            veil = pygame.Surface(SIZE, pygame.SRCALPHA)
            veil.fill((*BG, int((1 - app.phase_time / 0.20) * 180)))
            s.blit(veil, (0, 0))
        return s

    def eyebrow(self, label, color=CYAN):
        text(self.surface, label.upper(), (68, 203), 23, color, mono=True)

    def heading(self, title, color=WHITE, size=52):
        text(self.surface, title, (65, 246), size, color, bold=True)

    def setup(self, app):
        s, g = self.surface, app.game
        self.eyebrow("Initialisation / 04 équipes")
        self.heading("Qui entre dans la simulation ?")
        text(s, "Donnez un nom à chaque équipe, puis appuyez sur ENTRÉE.", (68, 312), 28, GRAY)
        for i, name in enumerate(g.names):
            x, y = 68 + (i % 2) * 756, 384 + (i // 2) * 138
            c = TEAM_COLORS[i]
            panel(s, (x, y, 712, 113), c, app.setup_index == i)
            text(s, f"0{i + 1}", (x + 22, y + 17), 24, c, mono=True)
            text(s, "ÉQUIPE", (x + 80, y + 18), 18, GRAY, mono=True)
            value = name + ("_" if app.setup_index == i and int(app.time * 2) % 2 == 0 else "")
            text(s, value, (x + 80, y + 47), 35, WHITE)
        text(s, "TAB / ↑ ↓  changer d'équipe     ·     24 caractères maximum", (68, 675), 23, GRAY, mono=True)

    def title(self, app):
        s, g = self.surface, app.game
        self.eyebrow("Simulation narrative / Palo Alto")
        words = g.scenario["title"].upper().split()
        split_at = max(1, len(words) - 1)
        for i, part in enumerate((" ".join(words[:split_at]), " ".join(words[split_at:]))):
            title_size = 89
            while font(title_size, bold=True).size(part)[0] > 826 and title_size > 40:
                title_size -= 1
            text(s, part, (62, 266 + i * 91), title_size, WHITE if i == 0 else CYAN, bold=True)
        paragraph(s, g.scenario["subtitle"], (68, 477), 760, 32, GRAY)
        pygame.draw.line(s, (43, 80, 94), (70, 582), (666, 582))
        text(s, "04 MANCHES   /   04 ÉQUIPES   /   05 POINTS", (70, 607), 24, WHITE, mono=True)
        text(s, "> ENTRÉE DANS LA SIMULATION_", (70, 665), 25, GREEN, mono=True)
        if app.network and app.network.session and g.mode == "ONLINE":
            self.lobby(app)
        else:
            signal(s, (1174, 408), 290, app.time)
            text(s, "CANAL // INTERACTION HUMAINE", (966, 665), 22, DIM, mono=True)
        if app.network and g.mode == "ONLINE":
            text(s, f"BACKEND : {'OK' if app.network.health_ok else 'TEST…'}   WEBSOCKET : {'OK' if app.network.socket_ok else 'TEST…'}", (70, 709), 19, GREEN if app.network.socket_ok else AMBER, mono=True)

    def lobby(self, app):
        s = self.surface
        session = app.network.session
        panel(s, (934, 194, 600, 500), CYAN, True)
        text(s, "REJOINDRE LA SESSION", (966, 214), 24, CYAN, mono=True)
        text(s, session["room_code"], (966, 257), 55, WHITE, mono=True, bold=True)
        url = session["mobile_url"]
        if self.qr_url != url:
            qr = qrcode.QRCode(box_size=8, border=4, error_correction=qrcode.constants.ERROR_CORRECT_M)
            qr.add_data(url)
            qr.make(fit=True)
            image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            self.qr = pygame.image.frombytes(image.tobytes(), image.size, "RGB")
            self.qr_url = url
        s.blit(pygame.transform.scale(self.qr, (288, 288)), (1090, 320))
        connected = len(app.connected)
        text(s, f"{connected}/4 CONTRÔLEURS CONNECTÉS", (966, 633), 24, GREEN if connected == 4 else GRAY, mono=True)
        text(s, "N : TEST RÉSEAU   /   F4 : MANUEL", (966, 667), 19, GRAY, mono=True)

    def intro(self, app):
        s = self.surface
        self.eyebrow("Brief de mission")
        self.heading("Une conversation. Vos décisions.")
        rows = [
            ("01", "INFLUENCER", "Votez pour la prochaine réplique. La majorité trace le chemin.", CYAN),
            ("02", "INTERPRÉTER", "Observez la scène, puis chaque équipe donne son analyse.", MAGENTA),
            ("03", "DÉCODER", "+1 point par analyse juste. Le diagnostic final vaut +2.", GREEN),
        ]
        for i, (num, label, detail, color) in enumerate(rows):
            y = 349 + i * 111
            text(s, num, (70, y), 53, color, mono=True)
            text(s, label, (179, y + 2), 25, color, mono=True)
            text(s, detail, (179, y + 42), 28, WHITE)
        text(s, "Vos répliques font avancer l'histoire. Vos analyses rapportent les points.", (70, 692), 26, GRAY)

    def scene(self, app):
        s, g = self.surface, app.game
        self.eyebrow(f"{'Branche ' + g.path if g.phase == Phase.BRANCH else g.node['skill']} / {g.node['location']}")
        self.heading(g.node["title"])
        panel(s, (68, 329, 1466, 359), CYAN if g.phase == Phase.SCENE else MAGENTA)
        line = g.lines[g.line_index]
        color = pygame.Color(g.scenario["characters"][line["speaker"]])
        text(s, line["speaker"].upper(), (104, 366), 28, color, mono=True, bold=True)
        text(s, f"FLUX / {g.line_index + 1:02d} — {len(g.lines):02d}", (1242, 369), 21, DIM, mono=True)
        amount = int(app.phase_time * g.scenario["timing"]["characters_per_second"])
        displayed = line["text"][:amount]
        cursor = " ▌" if int(app.time * 2) % 2 == 0 and amount < len(line["text"]) else ""
        size = 45
        while len(wrapped(line["text"], size, 1285)) > 4 and size > 30:
            size -= 1
        paragraph(s, displayed + cursor, (104, 422), 1285, size, GRAY if line["speaker"] == "Narrateur" else WHITE)
        for i in range(len(g.lines)):
            pygame.draw.circle(s, color if i == g.line_index else DIM, (111 + i * 24, 657), 4)
        text(s, "Écoutez. Observez. Chaque signe compte.", (104, 702), 24, GRAY)

    def input(self, app):
        s, g = self.surface, app.game
        vote = g.phase == Phase.VOTE
        c = CYAN if vote else MAGENTA
        self.eyebrow(f"{'Choisir la réplique' if vote else g.node['skill']} / {'Sans points' if vote else '+' + str(g.node['points']) + ' point' + ('s' if g.node['points'] > 1 else '')}", c)
        question = g.node["prompt"] if vote else g.analysis["question"]
        size = 48 if vote else 39
        bottom = paragraph(s, question, (65, 245), 1445, size, WHITE, bold=True, gap=2)
        start = max(334, bottom + 19)
        options = [(key, v["text"]) for key, v in g.node["choices"].items()] if vote else [(str(i + 1), v) for i, v in enumerate(g.analysis["answers"])]
        available = 674 - start
        height = min(108, (available - (len(options) - 1) * 13) // len(options))
        for i, (key, value) in enumerate(options):
            y = start + i * (height + 13)
            panel(s, (68, y, 1466, height), c)
            text(s, key, (94, y + (height - 48) // 2), 40, c, mono=True)
            pygame.draw.line(s, (40, 53, 67), (154, y + 20), (154, y + height - 20))
            font_size = 32
            while len(wrapped(value, font_size, 1322)) * (font(font_size).get_linesize() + 3) > height - 12 and font_size > 25:
                font_size -= 1
            lines = wrapped(value, font_size, 1322)
            yy = y + (height - len(lines) * (font(font_size).get_linesize() + 3)) // 2
            paragraph(s, value, (180, yy), 1322, font_size, WHITE, gap=3)
        if app.timer is not None:
            text(s, f"{math.ceil(app.timer):02d}s", (1430, 203), 30, AMBER, mono=True)
        if g.mode == "MANUAL":
            prompt = f"Équipe {g.selected_team + 1} sélectionnée > {'A / B / C' if vote else 'réponse 1–' + str(len(options))}" if g.selected_team is not None else "1–4 : sélectionner l'équipe, puis saisir sa réponse"
        else:
            prompt = "Les équipes choisissent sur leur téléphone. ESPACE quand les 4 réponses sont reçues."
        text(s, prompt if not g.complete else "4/4 VERROUILLÉES  >  ESPACE pour révéler", (70, 696), 26, GREEN if g.complete else GRAY)

    def vote_reveal(self, app):
        s, g = self.surface, app.game
        tied = g.path is None
        c = AMBER if tied else CYAN
        self.eyebrow("Conflit de vote / départage animateur" if tied else "Décisions dévoilées", c)
        self.heading("Égalité détectée." if tied else "Le chemin se dessine.", c)
        ease = min(1, app.phase_time / 0.8)
        for i, key in enumerate("ABC"):
            y = 352 + i * 108
            text(s, key, (73, y), 46, c if key in g.tied else GRAY, mono=True)
            for j in range(4):
                filled = j < g.tally[key] * ease
                pygame.draw.rect(s, c if filled else (26, 39, 51), (162 + j * 146, y + 8, 130, 43), border_radius=3)
            text(s, str(g.tally[key]), (782, y + 5), 38, WHITE, mono=True)
        panel(s, (955, 332, 578, 323), c)
        text(s, "JOURNAL DES DÉCISIONS", (981, 350), 20, GRAY, mono=True)
        for i in range(4):
            y = 409 + i * 55
            text(s, g.names[i], (981, y), 27, TEAM_COLORS[i])
            text(s, g.votes.get(i, "—"), (1462, y), 29, TEAM_COLORS[i], mono=True, bold=True)
        label = " / ".join(g.tied) + " : appuyez sur une option ex æquo" if g.phase == Phase.TIE else "ESPACE pour départager" if tied else f"CHEMIN RETENU : {g.path}  >  ESPACE pour jouer la scène"
        text(s, label, (70, 684), 30, c, mono=True)

    def analysis_reveal(self, app):
        s, g = self.surface, app.game
        self.eyebrow("Analyse confirmée / diagnostic" if g.round_index == 3 else "Analyse de l'interaction", GREEN)
        correct = g.analysis["correct"]
        text(s, f"0{correct}", (62, 281), 185, GREEN, mono=True, bold=True)
        text(s, "RÉPONSE", (78, 495), 24, GREEN, mono=True)
        panel(s, (377, 298, 1156, 378), GREEN, True)
        y = paragraph(s, g.analysis["label"], (408, 327), 1087, 43, WHITE, bold=True)
        y = paragraph(s, g.analysis["answers"][correct - 1], (411, y + 12), 1065, 30, GREEN)
        paragraph(s, g.analysis["explanation"], (411, y + 21), 1065, 29, GRAY)
        ax = " + ".join(f"0{a}" for a in g.analysis["axioms"])
        text(s, f"AXIOMES / {ax}", (70, 689), 24, CYAN, mono=True)
        # Thin signal sweep provides reveal emphasis without flashing the whole screen.
        if app.phase_time < 0.65:
            x = int(app.phase_time / 0.65 * 1460) + 70
            pygame.draw.line(s, GREEN, (x, 301), (x, 669), 2)

    def transition(self, app):
        s, g = self.surface, app.game
        self.eyebrow("Interaction enregistrée", GREEN)
        text(s, f"0{g.round_index + 1}", (60, 262), 132, DIM, mono=True, bold=True)
        text(s, "Signal décodé.", (322, 283), 70, WHITE, bold=True)
        text(s, "La conversation continue.", (326, 374), 38, GRAY)
        signal(s, (1181, 431), 230, app.time, 0.8)
        text(s, f"> PROCHAIN NŒUD / 0{g.round_index + 2}", (72, 541), 32, CYAN, mono=True)
        text(s, g.scenario["rounds"][g.round_index + 1]["title"], (72, 601), 38, WHITE)
        text(s, "ESPACE pour poursuivre  ·  F4 pour changer de mode", (72, 680), 26, GRAY)

    def final(self, app):
        s, g = self.surface, app.game
        self.eyebrow("Session complète", GREEN)
        self.heading("Vous avez décodé la conversation.")
        ordered = sorted(range(4), key=lambda i: -g.scores[i])
        ease = min(1, app.phase_time / 1.1)
        for order, team in enumerate(ordered):
            score = g.scores[team]
            rank = 1 + sum(value > score for value in g.scores)
            y = 338 + order * 87
            c = TEAM_COLORS[team]
            panel(s, (70, y, 1463, 75), c, rank == 1)
            text(s, f"0{rank}", (96, y + 10), 42, c, mono=True)
            text(s, g.names[team], (211, y + 17), 34, WHITE)
            if g.scores.count(score) > 1:
                text(s, "EX ÆQUO", (1036, y + 23), 23, GRAY, mono=True)
            text(s, f"{round(score * ease):02d} / 05", (1299, y + 18), 33, c, mono=True, bold=True)
        text(s, "5 axiomes. Plusieurs chemins. Une même communication en interaction.", (70, 699), 27, GRAY)

    def end(self, app):
        s = self.surface
        signal(s, (1199, 420), 262, app.time, 0.7)
        self.eyebrow("Transmission terminée", GREEN)
        text(s, "Communication", (62, 285), 77, WHITE, bold=True)
        text(s, "analysée.", (62, 374), 77, CYAN, bold=True)
        text(s, "> RETOUR À LA CONFÉRENCE" + ("_" if int(app.time * 2) % 2 == 0 else ""), (70, 550), 32, GREEN, mono=True)
        text(s, "Merci aux quatre équipes.", (70, 629), 30, GRAY)

    def teams(self, app):
        s, g = self.surface, app.game
        for i, name in enumerate(g.names):
            x, y, c = 68 + i * 373, 745, TEAM_COLORS[i]
            active = g.selected_team == i or (g.phase == Phase.SETUP and app.setup_index == i)
            panel(s, (x, y, 349, 83), c, active)
            text(s, f"0{i + 1}", (x + 15, y + 13), 19, c, mono=True)
            # Full names are fitted down to 20px; no truncation of configured identities.
            name_size = 25
            while font(name_size).size(name)[0] > 235 and name_size > 20:
                name_size -= 1
            shown_name = name
            while font(name_size).size(shown_name)[0] > 235:
                shown_name = shown_name[:-2] + "…"
            text(s, shown_name, (x + 52, y + 10), name_size, WHITE)
            if g.phase in (Phase.VOTE, Phase.ANALYSIS):
                status = "VERROUILLÉ" if i in g.answers else "EN ATTENTE"
                text(s, status, (x + 52, y + 48), 20, c if i in g.answers else GRAY, mono=True)
            else:
                if g.phase == Phase.ANALYSIS_REVEAL:
                    award = g.awards[i]
                    shown = g.scores[i] - award + round(award * min(1, app.phase_time / 0.8))
                    text(s, "RÉP. " + g.answers.get(i, "—"), (x + 52, y + 48), 19, c, mono=True)
                    text(s, f"{shown} PTS", (x + 183, y + 48), 19, GRAY, mono=True)
                    text(s, f"+{award}" if award else "×", (x + 278, y + 39), 31, GREEN if award else RED, mono=True)
                else:
                    text(s, f"{g.scores[i]} PTS", (x + 52, y + 48), 21, c, mono=True)
            if active:
                glow_dot(s, (x + 329, y + 64), c, 3)

    def footer(self, app):
        s = self.surface
        pygame.draw.line(s, (32, 43, 57), (68, 845), (1534, 845))
        text(s, "ESPACE  continuer     F1  aide     F11  plein écran", (70, 861), 19, GRAY, mono=True)
        text(s, "PALO ALTO / LES SIGNAUX FAIBLES", (1190, 861), 17, DIM, mono=True)

    def shade(self):
        veil = pygame.Surface(SIZE, pygame.SRCALPHA)
        veil.fill((0, 0, 0, 205))
        self.surface.blit(veil, (0, 0))

    def help(self):
        self.shade()
        s = self.surface
        panel(s, (263, 145, 1074, 608), CYAN, True)
        text(s, "CONSOLE / AIDE ANIMATEUR", (299, 169), 35, CYAN, mono=True)
        rows = [
            ("ESPACE / ENTRÉE", "Finir l'animation, puis continuer"),
            ("1–4 puis A/B/C", "Choix de l'équipe en mode manuel"),
            ("1–4 puis 1–4", "Analyse : équipe puis numéro de réponse"),
            ("RETOUR ARRIÈRE", "Annuler / rouvrir la dernière réponse"),
            ("F4 / N", "Manuel ↔ en ligne / test ou nouvelle connexion"),
            ("T / P", "Lancer ou arrêter le chrono / pause"),
            ("R / ÉCHAP", "Menu de reprise / confirmation de sortie"),
            ("F2 / F11 / F1", "HUD public / plein écran / fermer cette aide"),
        ]
        for i, (key, description) in enumerate(rows):
            y = 242 + i * 57
            text(s, key, (304, y), 24, CYAN, mono=True)
            text(s, description, (633, y), 25, WHITE)
        text(s, "Aucune bonne réponse n'est montrée dans le HUD.", (304, 709), 23, GRAY)

    def menu(self, app):
        self.shade()
        s = self.surface
        panel(s, (352, 233, 896, 429), AMBER, True)
        text(s, "CONFIRMATION / ANIMATEUR", (392, 263), 27, AMBER, mono=True)
        if app.menu == "exit":
            paragraph(s, "Terminer la session et quitter ?", (392, 329), 810, 42, WHITE, bold=True)
            text(s, "ENTRÉE  confirmer     ÉCHAP  annuler", (392, 543), 27, GRAY, mono=True)
        elif app.menu == "recovery":
            text(s, "Reprendre la simulation", (392, 331), 41, WHITE, bold=True)
            text(s, "R  Recommencer cette phase", (392, 412), 28, CYAN)
            text(s, "C  Recommencer cette manche (annule ses points)", (392, 465), 27, AMBER)
            text(s, "G  Nouvelle partie       ÉCHAP  annuler", (392, 536), 27, GRAY)
        else:
            labels = {"phase": "Recommencer la phase ?", "round": "Recommencer la manche ?", "game": "Créer une nouvelle partie ?"}
            paragraph(s, labels.get(app.menu, ""), (392, 329), 810, 42, WHITE, bold=True)
            text(s, "ENTRÉE  confirmer     ÉCHAP  annuler", (392, 543), 27, GRAY, mono=True)

    def error(self, message):
        self.eyebrow("Erreur de configuration", RED)
        self.heading("La simulation n'a pas pu démarrer.")
        paragraph(self.surface, message, (70, 354), 1425, 31, WHITE)
        text(self.surface, "Corrigez le fichier indiqué, puis relancez. ÉCHAP pour quitter.", (70, 650), 28, GRAY)
