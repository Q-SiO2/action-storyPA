"""Resolution-independent terminal primitives and procedural signal illustration."""
import math
import pygame
from functools import lru_cache

BG = (5, 7, 10)
WHITE = (232, 237, 242)
GRAY = (153, 166, 185)
DIM = (73, 90, 110)
CYAN = (51, 230, 255)
MAGENTA = (255, 79, 216)
GREEN = (92, 255, 133)
AMBER = (255, 200, 87)
RED = (255, 92, 115)
TEAM_COLORS = [CYAN, MAGENTA, GREEN, AMBER]


@lru_cache(maxsize=100)
def font(size, mono=False, bold=False):
    candidates = "consolas,dejavusansmono,liberationmono" if mono else "bahnschrift,segoeui,dejavusans"
    return pygame.font.SysFont(candidates, size, bold=bold)


def text(surface, value, xy, size=28, color=WHITE, mono=False, bold=False):
    rendered = font(size, mono, bold).render(str(value), True, color)
    surface.blit(rendered, xy)
    return rendered.get_rect(topleft=xy)


def wrapped(value, size, width, mono=False, bold=False):
    f = font(size, mono, bold)
    result = []
    for paragraph in str(value).split("\n"):
        line = ""
        for word in paragraph.split():
            if f.size((line + " " + word).strip())[0] > width and line:
                result.append(line)
                line = ""
            if f.size(word)[0] > width:
                if line:
                    result.append(line)
                    line = ""
                for char in word:
                    if f.size(line + char)[0] > width:
                        result.append(line)
                        line = char
                    else:
                        line += char
                continue
            line = (line + " " + word).strip()
        result.append(line)
    return result


def paragraph(surface, value, xy, width, size=32, color=WHITE, mono=False, bold=False, gap=7):
    lines = wrapped(value, size, width, mono, bold)
    x, y = xy
    height = font(size, mono, bold).get_linesize() + gap
    for line in lines:
        text(surface, line, (x, y), size, color, mono, bold)
        y += height
    return y


def panel(surface, rect, accent=CYAN, active=False):
    rect = pygame.Rect(rect)
    pygame.draw.rect(surface, (11, 17, 25), rect, border_radius=10)
    pygame.draw.rect(surface, accent if active else (36, 50, 65), rect, 1, border_radius=10)
    pygame.draw.line(surface, accent, (rect.x, rect.y + 18), (rect.x, rect.y + 45), 3)
    return rect


def glow_dot(surface, xy, color, radius=5):
    halo = pygame.Surface((radius * 12, radius * 12), pygame.SRCALPHA)
    center = (radius * 6, radius * 6)
    for r in range(radius * 5, radius, -2):
        pygame.draw.circle(halo, (*color, 6), center, r)
    pygame.draw.circle(halo, (*color, 255), center, radius)
    surface.blit(halo, (xy[0] - center[0], xy[1] - center[1]))


def signal(surface, center, radius, t, intensity=1):
    """Orbital message paths: a vector motif, never a blocking game mechanic."""
    x, y = center
    layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    for r in range(90, 4, -5):
        pygame.draw.circle(layer, (*CYAN, 3), center, r)
    for i in range(5):
        points = []
        for j in range(181):
            a = j / 180 * math.tau
            r = radius * (0.50 + i * 0.10)
            px = math.cos(a) * r
            py = math.sin(a) * r * (0.32 + i * 0.05)
            rotation = i * 0.48 + t * 0.035
            points.append((x + px * math.cos(rotation) - py * math.sin(rotation),
                           y + px * math.sin(rotation) + py * math.cos(rotation)))
        color = CYAN if i % 2 == 0 else MAGENTA
        pygame.draw.aalines(layer, (*color, int(150 * intensity)), True, points)
        pos = points[int((t * (12 + i * 2) + i * 28) % 180)]
        for r in (14, 10, 6):
            pygame.draw.circle(layer, (*color, 12), pos, r)
        pygame.draw.circle(layer, (*color, 230), pos, 3)
    pygame.draw.circle(layer, (*CYAN, 170), center, 4)
    surface.blit(layer, (0, 0))


def progress(surface, completed, y=148):
    for i in range(4):
        x = 66 + i * 369
        color = TEAM_COLORS[i] if i <= completed else DIM
        pygame.draw.line(surface, color, (x, y), (x + 333, y), 2)
        text(surface, f"0{i + 1}", (x, y - 28), 19, color, mono=True)
