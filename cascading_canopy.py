from __future__ import annotations

"""
cascading_canopy.py

Canopy Cascade mini-game for The Shifting Grove.

This module implements a standalone falling-object challenge that can also be
embedded inside the main maze game. The explorer and fox compete to catch their
matching magical items while avoiding curses. The winner selects a reward that is
returned to game.py, where the main maze applies the reward effect.

This file owns Canopy Cascade's internal systems:
- intro and instruction flow
- countdown and timed gameplay
- weighted item spawning and difficulty scaling
- explorer input and fox basket control
- single-player fox AI behavior
- collision, scoring, particles, and screen shake
- result, reward selection, and completion flow

game.py is responsible only for starting this mini-game, updating/drawing it
while the maze is paused, and applying the selected reward after completion.
"""

import math
import random
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import pygame

try:
    from settings import FANTASY_FONT
except Exception:
    FANTASY_FONT = None


# =============================================================================
# Configuration
# =============================================================================

SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
FPS = 60

INTRO_SECONDS = 3.0
COUNTDOWN_SECONDS = 3.0
COUNTDOWN_GO_SECONDS = 0.65
ROUND_SECONDS = 30.0
RESULT_PAUSE_SECONDS = 1.0
DEFAULT_GAME_MODE = "single"

BASE_DIR = Path(__file__).resolve().parent
ASSET_DIRS = [BASE_DIR / "assets" / "images", Path.cwd() / "assets" / "images"]

ASSETS = {
    "background": "canopy_cascade_background.png",
    "acorn": "canopy_cascade_acorn.png",
    "moonberry": "canopy_cascade_moonberries.png",
    "explorer_basket": "cchumanbasket.png",
    "fox_basket": "ccfoxbasket.png",
    "minus_two": "ccminustwo.png",
    "freeze": "ccfreeze.png",
    "hourglass_full": "hourglass_full.png",
    "hourglass_empty": "hourglass_empty.png",
}

CINEMATIC_SCREENS = {
    "explorer_wins": "canopy_cascade_explorer_wins.png",
    "fox_wins": "canopy_cascade_fox_wins.png",
    "tie": "canopy_cascade_tie.png",
    "complete": "canopy_cascade_complete.png",
    "explorer_choose": "canopy_cascade_explorer_choose_reward.png",
    "fox_choose": "canopy_cascade_fox_choose_reward.png",
    "reward_grove_calm": "canopy_cascade_reward_grove_calm.png",
    "reward_lantern_shield": "canopy_cascade_reward_lantern_shield.png",
    "reward_fox_banish": "canopy_cascade_reward_fox_banish.png",
    "reward_mischief_surge": "canopy_cascade_reward_mischief_surge.png",
    "reward_shadow_rush": "canopy_cascade_reward_shadow_rush.png",
    "reward_portal_flicker": "canopy_cascade_reward_portal_flicker.png",
}

EXPLORER_REWARD_KEYS = [
    "reward_grove_calm",
    "reward_lantern_shield",
    "reward_fox_banish",
]
FOX_REWARD_KEYS = [
    "reward_mischief_surge",
    "reward_shadow_rush",
    "reward_portal_flicker",
]

# These IDs match the reward IDs already used by Sigils Echo and
# Starlight Crossing, so game.py can apply the same reward effects.
REWARD_KEY_TO_GAME_ID = {
    "reward_grove_calm": "grove_calm",
    "reward_lantern_shield": "lantern_shield",
    "reward_fox_banish": "fox_banish",
    "reward_mischief_surge": "mischief_surge",
    "reward_shadow_rush": "shadow_rush",
    "reward_portal_flicker": "portal_flicker",
}

TEXT_MAIN = (244, 250, 255)
TEXT_SOFT = (198, 224, 230)
TEAL = (92, 243, 211)
PURPLE = (196, 127, 255)
GOLD = (255, 223, 140)
RED = (255, 108, 108)
ICE = (151, 231, 255)
SHADOW = (0, 0, 0)
DARK_OVERLAY = (4, 12, 10)
PANEL_GREEN = (8, 30, 24)
PANEL_BORDER = (130, 230, 200)

SPAWN = {
    "start_interval": 0.43,
    "end_interval": 0.25,
    "jitter": (-0.045, 0.08),
    "start_speed_mult": 1.0,
    "end_speed_mult": 1.30,
    "max_active": 13,
    "max_curses": 3,
    "min_curse_gap": 0.80,
    "x_margin": 68,
    "spawn_y": (-155, -55),
    "good_balance_bonus": 0.12,
}

PLAYER = {
    "basket_y": SCREEN_HEIGHT - 34,
    "speed": 470.0,
    "ai_fox_speed": 430.0,
    "freeze_seconds": 1.55,
    "catch_shrink_x": 22,
    "catch_top_pad": 16,
    "catch_bottom_pad": 10,
}

AI = {
    "reaction_delay": (0.14, 0.28),
    "mistake_chance": 0.08,
    "jitter_px": 22,
    "deadzone": 15,
    "avoid_radius": 94,
    "danger_y": SCREEN_HEIGHT - 210,
    "patrol_left": SCREEN_WIDTH * 0.60,
    "patrol_right": SCREEN_WIDTH * 0.90,
    "losing_speed_bonus": 95.0,
    "final_seconds_speed_bonus": 65.0,
    "large_deficit_threshold": 5,
    "small_deficit_threshold": 2,
    "pressure_reaction_multiplier": 0.55,
    "pressure_mistake_reduction": 0.055,
}

SEQUENCE = {
    "winner_seconds": 3.8,
    "winner_fade_in_seconds": 1.2,
    "reward_transition_seconds": 1.0,
    "reward_hold_seconds": 3.6,
    "complete_hold_seconds": 3.2,
    "claimed_to_complete_transition_seconds": 1.0,
    "fox_ai_choice_delay": 2.0,
}

# =============================================================================
# Enums / dataclasses
# =============================================================================


class GameState(Enum):
    TRANSITION = "transition"
    INSTRUCTIONS = "instructions"
    COUNTDOWN = "countdown"
    GAMEPLAY = "gameplay"
    RESULT_PAUSE = "result_pause"
    RESULT = "result"
    DONE = "done"


class ItemKind(Enum):
    MOONBERRY = "moonberry"
    ACORN = "acorn"
    MINUS_TWO = "minus_two"
    FREEZE = "freeze"


@dataclass(frozen=True)
class ItemConfig:
    kind: ItemKind
    asset_key: str
    weight: float
    size: tuple[int, int]
    speed: tuple[float, float]
    target_owner: Optional[str] = None
    score_delta: int = 0
    is_curse: bool = False
    popup: str = ""
    popup_color: tuple[int, int, int] = TEXT_MAIN


ITEMS = {
    ItemKind.MOONBERRY: ItemConfig(ItemKind.MOONBERRY, "moonberry", 0.39, (72, 72), (245, 360), "explorer", 1, False, "+1", TEAL),
    ItemKind.ACORN: ItemConfig(ItemKind.ACORN, "acorn", 0.39, (70, 70), (245, 360), "fox", 1, False, "+1", PURPLE),
    ItemKind.MINUS_TWO: ItemConfig(ItemKind.MINUS_TWO, "minus_two", 0.13, (66, 66), (255, 375), None, -2, True, "-2", RED),
    ItemKind.FREEZE: ItemConfig(ItemKind.FREEZE, "freeze", 0.09, (66, 66), (250, 355), None, 0, True, "Frozen!", ICE),
}


# =============================================================================
# Helpers
# =============================================================================


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def lerp(start: float, end: float, amount: float) -> float:
    return start + (end - start) * amount


def smoothstep(value: float) -> float:
    value = clamp(value, 0.0, 1.0)
    return value * value * (3.0 - 2.0 * value)


def phase(progress: float, start: float, end: float) -> float:
    if end <= start:
        return 1.0
    return smoothstep((progress - start) / (end - start))


def weighted_choice(options: list[tuple[ItemKind, float]], rng: random.Random) -> ItemKind:
    total = sum(max(0.0, weight) for _, weight in options)
    if total <= 0:
        return ItemKind.MOONBERRY
    roll = rng.uniform(0.0, total)
    current = 0.0
    for kind, weight in options:
        current += max(0.0, weight)
        if roll <= current:
            return kind
    return options[-1][0]


def wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_centered_text(surface, font, text, color, center, alpha=255) -> pygame.Rect:
    image = font.render(text, True, color)
    image.set_alpha(alpha)
    rect = image.get_rect(center=center)
    surface.blit(image, rect)
    return rect


def draw_shadowed_text(surface, font, text, color, center, alpha=255, offset=3) -> pygame.Rect:
    shadow = font.render(text, True, SHADOW)
    shadow.set_alpha(alpha)
    surface.blit(shadow, shadow.get_rect(center=(center[0] + offset, center[1] + offset)))
    image = font.render(text, True, color)
    image.set_alpha(alpha)
    rect = image.get_rect(center=center)
    surface.blit(image, rect)
    return rect


# =============================================================================
# Asset and font systems
# =============================================================================


class FontBook:
    def __init__(self) -> None:
        self.cache: dict[int, pygame.font.Font] = {}

    def get(self, size: int) -> pygame.font.Font:
        if size not in self.cache:
            if FANTASY_FONT and Path(FANTASY_FONT).exists():
                self.cache[size] = pygame.font.Font(str(FANTASY_FONT), size)
            else:
                self.cache[size] = pygame.font.Font(None, size)
        return self.cache[size]


class AssetManager:
    def __init__(self, fonts: FontBook) -> None:
        self.fonts = fonts
        self.images: dict[str, Optional[pygame.Surface]] = {}
        self.screen_cache: dict[str, Optional[pygame.Surface]] = {}
        self.load_all()

    def path_for(self, filename: str) -> Optional[Path]:
        for folder in ASSET_DIRS:
            path = folder / filename
            if path.exists():
                return path
        return None

    def load_image(self, key: str, exact=None, max_size=None, optional=False) -> Optional[pygame.Surface]:
        image = None
        path = self.path_for(ASSETS[key])
        if path:
            try:
                image = pygame.image.load(str(path)).convert_alpha()
            except pygame.error:
                image = None
        if image is None:
            if optional:
                return None
            image = self.fallback_for(key)
        if exact:
            return pygame.transform.smoothscale(image, exact)
        if max_size:
            w, h = image.get_size()
            scale = min(max_size[0] / w, max_size[1] / h, 1.0)
            if scale != 1.0:
                image = pygame.transform.smoothscale(image, (max(1, int(w * scale)), max(1, int(h * scale))))
        return image

    def load_all(self) -> None:
        self.images["background"] = self.load_image("background", exact=(SCREEN_WIDTH, SCREEN_HEIGHT))
        for _, config in ITEMS.items():
            self.images[config.asset_key] = self.load_image(config.asset_key, max_size=config.size)
        self.images["explorer_basket"] = self.load_image("explorer_basket", max_size=(170, 120))
        self.images["fox_basket"] = self.load_image("fox_basket", max_size=(170, 120))
        self.images["hourglass_full"] = self.load_image("hourglass_full", max_size=(66, 66), optional=True)
        self.images["hourglass_empty"] = self.load_image("hourglass_empty", max_size=(66, 66), optional=True)

    def get(self, key: str) -> pygame.Surface:
        image = self.images.get(key)
        if image is None:
            image = self.fallback_for(key)
            self.images[key] = image
        return image

    def get_screen(self, key: str) -> Optional[pygame.Surface]:
        if key in self.screen_cache:
            return self.screen_cache[key]
        filename = CINEMATIC_SCREENS.get(key)
        if not filename:
            self.screen_cache[key] = None
            return None
        path = self.path_for(filename)
        image = None
        if path:
            try:
                image = pygame.image.load(str(path)).convert_alpha()
                image = pygame.transform.smoothscale(image, (SCREEN_WIDTH, SCREEN_HEIGHT))
            except pygame.error:
                image = None
        self.screen_cache[key] = image
        return image

    def fallback_for(self, key: str) -> pygame.Surface:
        if key == "background":
            return self.make_background()
        if key == "moonberry":
            return self.make_moonberries(64)
        if key == "acorn":
            return self.make_acorn(58)
        if key == "minus_two":
            return self.make_circle(58, (180, 52, 52), (255, 185, 185), "-2")
        if key == "freeze":
            return self.make_freeze(58)
        if key == "explorer_basket":
            return self.make_basket((154, 88), (133, 90, 42), TEAL)
        if key == "fox_basket":
            return self.make_basket((154, 88), (77, 50, 95), PURPLE)
        return self.make_circle(64, (150, 50, 180), (255, 255, 255), "?")

    def make_background(self) -> pygame.Surface:
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        for y in range(SCREEN_HEIGHT):
            t = y / SCREEN_HEIGHT
            pygame.draw.line(surf, (int(9 + 8 * t), int(35 + 26 * t), int(23 + 14 * t)), (0, y), (SCREEN_WIDTH, y))
        for x in range(-40, SCREEN_WIDTH + 80, 90):
            pygame.draw.circle(surf, (8, 48, 31), (x, 35), 70)
            pygame.draw.circle(surf, (6, 38, 26), (x + 38, 10), 62)
        pygame.draw.ellipse(surf, (10, 52, 32), (-80, SCREEN_HEIGHT - 130, SCREEN_WIDTH + 160, 210))
        return surf.convert()

    def make_circle(self, size, fill, outline, symbol) -> pygame.Surface:
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size // 2
        pygame.draw.circle(surf, (*outline, 220), (c, c), c - 2)
        pygame.draw.circle(surf, (*fill, 240), (c, c), c - 7)
        pygame.draw.circle(surf, (255, 255, 255, 42), (c - 8, c - 8), max(2, size // 5))
        text = self.fonts.get(int(size * 0.55)).render(symbol, True, TEXT_MAIN)
        surf.blit(text, text.get_rect(center=(c, c + 1)))
        return surf

    def make_basket(self, size, color, accent) -> pygame.Surface:
        w, h = size
        surf = pygame.Surface(size, pygame.SRCALPHA)
        body = pygame.Rect(8, h // 3, w - 16, h // 2)
        pygame.draw.ellipse(surf, (30, 20, 10, 80), (8, h - 18, w - 16, 14))
        pygame.draw.ellipse(surf, color, body)
        pygame.draw.ellipse(surf, accent, body, 4)
        pygame.draw.ellipse(surf, accent, pygame.Rect(6, h // 3 - 6, w - 12, 18))
        for i in range(7):
            x = int(18 + i * ((w - 36) / 6))
            pygame.draw.line(surf, (115, 78, 35), (x, h // 3 + 14), (x, h - 26), 3)
        for i in range(5):
            y = h // 3 + 18 + i * 10
            pygame.draw.line(surf, (123, 90, 42), (18, y), (w - 18, y), 3)
        return surf

    def make_acorn(self, size) -> pygame.Surface:
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.ellipse(surf, (120, 65, 25), pygame.Rect(int(size * 0.30), int(size * 0.32), int(size * 0.40), int(size * 0.46)))
        pygame.draw.ellipse(surf, (118, 65, 165), pygame.Rect(int(size * 0.24), int(size * 0.18), int(size * 0.52), int(size * 0.28)))
        pygame.draw.rect(surf, (75, 42, 22), pygame.Rect(int(size * 0.48), int(size * 0.11), max(2, int(size * 0.05)), int(size * 0.14)), border_radius=2)
        return surf

    def make_moonberries(self, size) -> pygame.Surface:
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        for bx, by in [(0.42, 0.56), (0.56, 0.56), (0.49, 0.42)]:
            pygame.draw.circle(surf, (114, 255, 235), (int(size * bx), int(size * by)), int(size * 0.16))
            pygame.draw.circle(surf, (220, 255, 248), (int(size * bx - 4), int(size * by - 4)), int(size * 0.05))
        pygame.draw.line(surf, (80, 160, 90), (int(size * 0.48), int(size * 0.18)), (int(size * 0.48), int(size * 0.38)), 4)
        pygame.draw.line(surf, (80, 160, 90), (int(size * 0.48), int(size * 0.28)), (int(size * 0.40), int(size * 0.38)), 3)
        pygame.draw.line(surf, (80, 160, 90), (int(size * 0.48), int(size * 0.28)), (int(size * 0.58), int(size * 0.38)), 3)
        return surf

    def make_freeze(self, size) -> pygame.Surface:
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size // 2
        pygame.draw.circle(surf, (10, 82, 120, 170), (c, c), c - 4)
        pygame.draw.circle(surf, (190, 240, 255, 220), (c, c), c - 4, 3)
        for angle in range(0, 180, 45):
            rad = math.radians(angle)
            dx = math.cos(rad) * size * 0.24
            dy = math.sin(rad) * size * 0.24
            pygame.draw.line(surf, (230, 250, 255), (c - dx, c - dy), (c + dx, c + dy), 4)
        pygame.draw.circle(surf, (225, 248, 255), (c, c), 6)
        return surf


# =============================================================================
# Transition and instructions
# =============================================================================


class IntroDrop:
    def __init__(self, image, x, delay, target_y, scale, rng: random.Random) -> None:
        self.image = image
        self.x = x
        self.start_y = rng.randint(-340, -75)
        self.target_y = target_y
        self.delay = delay
        self.scale = scale
        self.base_rotation = rng.uniform(-38, 38)
        self.rotation_speed = rng.uniform(-3.1, 3.1)
        self.sway_offset = rng.uniform(0, math.tau)
        self.sway_amount = rng.uniform(8, 22)
        self.horizontal_drift = rng.uniform(-95, 95)
        self.drop_bounce = rng.uniform(8, 20)

    def draw(self, surface, progress, time_value) -> None:
        local = phase(progress, self.delay, self.delay + 0.22)
        if local <= 0:
            return
        y = lerp(self.start_y, self.target_y, local) + math.sin(local * math.pi) * -self.drop_bounce
        drift = max(0.0, 1.0 - local)
        x = self.x + self.horizontal_drift * drift + math.sin(time_value * 2.8 + self.sway_offset) * self.sway_amount * drift
        image = pygame.transform.rotozoom(self.image, self.base_rotation + self.rotation_speed * 55 * local, self.scale)
        surface.blit(image, image.get_rect(center=(int(x), int(y))))


class IntroScene:
    def __init__(self, assets: AssetManager, fonts: FontBook) -> None:
        self.assets = assets
        self.fonts = fonts
        self.timer = 0.0
        self.objects = self.build_objects()

    def build_objects(self) -> list[IntroDrop]:
        rng = random.Random(42)
        acorn = self.assets.get("acorn")
        berry = self.assets.get("moonberry")
        images = [acorn] * 20 + [berry] * 20
        rng.shuffle(images)
        objects: list[IntroDrop] = []
        for i, image in enumerate(images):
            scale = rng.uniform(0.42, 0.58) if image == acorn else rng.uniform(0.38, 0.54)
            target_x = rng.randint(150, 875)
            target_y = rng.choice([670, 652, 634, 616, 598]) + rng.randint(-8, 8)
            delay = 0.06 + i * 0.018 + rng.uniform(-0.008, 0.014)
            objects.append(IntroDrop(image, target_x + rng.randint(-130, 130), delay, target_y, scale, rng))
        return objects

    def progress(self) -> float:
        return clamp(self.timer / INTRO_SECONDS, 0.0, 1.0)

    def is_complete(self) -> bool:
        return self.timer >= INTRO_SECONDS

    def skip(self) -> None:
        self.timer = INTRO_SECONDS

    def update(self, dt) -> None:
        self.timer = min(INTRO_SECONDS, self.timer + dt)

    def draw(self, surface) -> None:
        p = self.progress()
        surface.blit(self.assets.get("background"), (0, 0))
        self.draw_pile_shadow(surface, p)
        for obj in self.objects:
            obj.draw(surface, p, pygame.time.get_ticks() / 1000.0)
        self.draw_overlay(surface, p)
        self.draw_title(surface, p)
        self.draw_hint(surface, p)

    def draw_pile_shadow(self, surface, p) -> None:
        amount = phase(p, 0.20, 0.58)
        if amount <= 0:
            return
        layer = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        pygame.draw.ellipse(layer, (0, 0, 0, int(110 * amount)), pygame.Rect(125, 600, 785, 122))
        pygame.draw.ellipse(layer, (45, 70, 40, int(45 * amount)), pygame.Rect(190, 615, 660, 82))
        surface.blit(layer, (0, 0))

    def draw_overlay(self, surface, p) -> None:
        amount = phase(p, 0.55, 0.82)
        if amount <= 0:
            return
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((*DARK_OVERLAY, int(76 * amount)))
        surface.blit(overlay, (0, 0))
        glow = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for width, alpha in [(820, 28), (650, 44), (480, 58)]:
            rect = pygame.Rect(SCREEN_WIDTH // 2 - width // 2, 330 - int(width * 0.34) // 2, width, int(width * 0.34))
            pygame.draw.ellipse(glow, (8, 34, 25, int(alpha * amount)), rect)
        surface.blit(glow, (0, 0))

    def draw_title(self, surface, p) -> None:
        amount = phase(p, 0.82, 0.94)
        if amount <= 0:
            return
        alpha = int(255 * amount)
        draw_shadowed_text(surface, self.fonts.get(76), "Canopy Cascade", TEXT_MAIN, (SCREEN_WIDTH // 2, 322), alpha)
        draw_centered_text(surface, self.fonts.get(27), "Catch your magic. Avoid the Grove's tricks.", TEXT_SOFT, (SCREEN_WIDTH // 2, 382), alpha)

    def draw_hint(self, surface, p) -> None:
        if p < 0.92:
            return
        blink = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.007)
        alpha = int((95 + blink * 135) * phase(p, 0.92, 0.99))
        draw_centered_text(surface, self.fonts.get(24), "Press SPACE to continue", TEXT_MAIN, (SCREEN_WIDTH // 2, 444), alpha)


class InstructionScreen:
    def __init__(self, assets: AssetManager, fonts: FontBook) -> None:
        self.assets = assets
        self.fonts = fonts
        self.timer = 0.0

    def reset(self) -> None:
        self.timer = 0.0

    def update(self, dt) -> None:
        self.timer += dt

    def draw(self, surface, game_mode: str) -> None:
        fade = smoothstep(clamp(self.timer / 0.75, 0.0, 1.0))

        surface.blit(self.assets.get("background"), (0, 0))

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((*DARK_OVERLAY, int(118 * fade)))
        surface.blit(overlay, (0, 0))

        # Main title.
        draw_shadowed_text(
            surface,
            self.fonts.get(62),
            "How to Play",
            TEXT_MAIN,
            (SCREEN_WIDTH // 2, 160),
            int(255 * fade),
            3,
        )

        # Smaller, centered instruction panel.
        panel_width = 720
        panel_height = 285
        panel = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        panel_rect = panel.get_rect(center=(SCREEN_WIDTH // 2, 405))

        pygame.draw.rect(
            panel,
            (*PANEL_GREEN, int(178 * fade)),
            panel.get_rect(),
            border_radius=28,
        )

        pygame.draw.rect(
            panel,
            (*PANEL_BORDER, int(130 * fade)),
            panel.get_rect(),
            2,
            border_radius=28,
        )

        # Subtle inner border so the panel feels polished.
        inner_rect = panel.get_rect().inflate(-12, -12)
        pygame.draw.rect(
            panel,
            (255, 255, 255, int(26 * fade)),
            inner_rect,
            1,
            border_radius=22,
        )

        surface.blit(panel, panel_rect)

        # Instruction text.
        bullets = [
            "Explorer catches moonberries.",
            "Fox catches acorns.",
            "Avoid -2 and freeze drops.",
            "Highest score wins when the timer ends.",
            "Explorer: A / D     Fox: LEFT / RIGHT",
        ]

        font = self.fonts.get(23)
        bullet_x = panel_rect.left + 62
        text_x = bullet_x + 32
        y = panel_rect.top + 46

        for line in bullets:
            pygame.draw.circle(
                surface,
                (150, 235, 226),
                (bullet_x, y + 13),
                5,
            )

            text = font.render(line, True, TEXT_MAIN).convert_alpha()
            text.set_alpha(int(255 * fade))
            surface.blit(text, (text_x, y))

            y += 42

        # Start prompt.
        blink = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.007)

        draw_centered_text(
            surface,
            self.fonts.get(25),
            "Press SPACE to start",
            TEXT_MAIN,
            (SCREEN_WIDTH // 2, 670),
            int((120 + blink * 120) * fade),
        )


# =============================================================================
# Visual feedback systems
# =============================================================================


class Particle:
    def __init__(self, pos, color, velocity, radius, lifetime) -> None:
        self.x = float(pos[0])
        self.y = float(pos[1])
        self.vx = float(velocity[0])
        self.vy = float(velocity[1])
        self.color = color
        self.radius = float(radius)
        self.lifetime = float(lifetime)
        self.timer = float(lifetime)

    def update(self, dt) -> None:
        self.timer -= dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vx *= 0.985
        self.vy *= 0.985
        self.radius = max(0.1, self.radius - dt * 3.5)

    def alive(self) -> bool:
        return self.timer > 0

    def draw(self, surface) -> None:
        if self.timer <= 0:
            return
        alpha = int(255 * max(0.0, self.timer / self.lifetime))
        radius = max(1, int(self.radius))
        layer = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
        center = layer.get_width() // 2
        pygame.draw.circle(layer, (*self.color, alpha), (center, center), radius)
        pygame.draw.circle(layer, (255, 255, 255, min(90, alpha)), (center, center), max(1, radius // 2))
        surface.blit(layer, layer.get_rect(center=(int(self.x), int(self.y))))


class FloatingText:
    def __init__(self, text, pos, color, font, lifetime=0.9) -> None:
        self.text = text
        self.x, self.y = float(pos[0]), float(pos[1])
        self.color = color
        self.font = font
        self.lifetime = lifetime
        self.timer = lifetime

    def update(self, dt) -> None:
        self.timer -= dt
        self.y -= 42 * dt

    def alive(self) -> bool:
        return self.timer > 0

    def draw(self, surface) -> None:
        alpha = int(255 * max(0.0, self.timer / self.lifetime))
        draw_shadowed_text(surface, self.font, self.text, self.color, (int(self.x), int(self.y)), alpha, 2)


# =============================================================================
# Gameplay entities
# =============================================================================


class FallingItem:
    def __init__(self, config: ItemConfig, image, x, y, speed, rng: random.Random) -> None:
        self.config = config
        self.kind = config.kind
        self.image = image
        self.x = float(x)
        self.y = float(y)
        self.speed = float(speed)
        self.rotation = rng.uniform(0, 360)
        self.rotation_speed = rng.uniform(-90, 90)
        self.scale = rng.uniform(0.90, 1.08)

    def update(self, dt) -> None:
        self.y += self.speed * dt
        self.rotation = (self.rotation + self.rotation_speed * dt) % 360

    def draw(self, surface) -> None:
        image = pygame.transform.rotozoom(self.image, self.rotation, self.scale)
        rect = image.get_rect(center=(int(self.x), int(self.y)))
        shadow = pygame.Surface((rect.width + 10, rect.height + 10), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 40), shadow.get_rect())
        surface.blit(shadow, (rect.x - 5, rect.y - 3))
        surface.blit(image, rect)

    def collision_rect(self) -> pygame.Rect:
        width = int(self.image.get_width() * self.scale * 0.74)
        height = int(self.image.get_height() * self.scale * 0.74)
        return pygame.Rect(int(self.x - width / 2), int(self.y - height / 2), width, height)

    def offscreen(self) -> bool:
        return self.y > SCREEN_HEIGHT + 90

    def time_to_y(self, y) -> float:
        return max(0.0, (y - self.y) / max(1.0, self.speed))


class Basket:
    def __init__(self, owner, image, x, y, speed, color) -> None:
        self.owner = owner
        self.image = image
        self.x = float(x)
        self.y = float(y)
        self.speed = float(speed)
        self.color = color
        self.frozen_until = 0.0
        self.flash_timer = 0.0

    @property
    def width(self):
        return self.image.get_width()

    @property
    def height(self):
        return self.image.get_height()

    def rect(self) -> pygame.Rect:
        return self.image.get_rect(midbottom=(int(self.x), int(self.y)))

    def catch_rect(self) -> pygame.Rect:
        rect = self.rect()
        sx = PLAYER["catch_shrink_x"]
        top = PLAYER["catch_top_pad"]
        bottom = PLAYER["catch_bottom_pad"]
        return pygame.Rect(rect.left + sx, rect.top + top, rect.width - sx * 2, rect.height - top - bottom)

    def frozen(self, now) -> bool:
        return now < self.frozen_until

    def freeze(self, now) -> None:
        self.frozen_until = max(self.frozen_until, now + PLAYER["freeze_seconds"])

    def update(self, dt, move_dir, now) -> None:
        self.flash_timer = max(0.0, self.flash_timer - dt)
        if self.frozen(now):
            return
        self.x += move_dir * self.speed * dt
        self.x = clamp(self.x, self.width / 2 + 16, SCREEN_WIDTH - self.width / 2 - 16)

    def draw(self, surface, now) -> None:
        rect = self.rect()
        if self.frozen(now):
            glow = pygame.Surface((rect.width + 18, rect.height + 14), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (110, 210, 255, 72), glow.get_rect())
            surface.blit(glow, (rect.x - 9, rect.y - 5))
        elif self.flash_timer > 0:
            glow = pygame.Surface((rect.width + 20, rect.height + 16), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (*self.color, 58), glow.get_rect())
            surface.blit(glow, (rect.x - 10, rect.y - 5))
        surface.blit(self.image, rect)


# =============================================================================
# Spawn and AI systems
# =============================================================================


class SpawnDirector:
    def __init__(self, rng: random.Random, assets: AssetManager) -> None:
        self.rng = rng
        self.assets = assets
        self.timer = 0.0
        self.curse_gap = 0.0
        self.good_counts = {ItemKind.MOONBERRY: 0, ItemKind.ACORN: 0}

    def reset(self) -> None:
        self.timer = 0.0
        self.curse_gap = 0.0
        self.good_counts = {ItemKind.MOONBERRY: 0, ItemKind.ACORN: 0}

    def difficulty(self, elapsed) -> float:
        return clamp(elapsed / ROUND_SECONDS, 0.0, 1.0)

    def update(self, dt, elapsed, active: list[FallingItem]) -> list[FallingItem]:
        self.timer -= dt
        self.curse_gap = max(0.0, self.curse_gap - dt)
        spawned = []
        if len(active) >= SPAWN["max_active"]:
            return spawned
        diff = self.difficulty(elapsed)
        interval = lerp(SPAWN["start_interval"], SPAWN["end_interval"], diff)
        while self.timer <= 0 and len(active) + len(spawned) < SPAWN["max_active"]:
            spawned.append(self.spawn_one(diff, active + spawned))
            low, high = SPAWN["jitter"]
            self.timer += max(0.12, interval + self.rng.uniform(low, high))
        return spawned

    def spawn_one(self, diff, active: list[FallingItem]) -> FallingItem:
        kind = self.choose_kind(active)
        config = ITEMS[kind]
        if config.is_curse:
            self.curse_gap = SPAWN["min_curse_gap"]
        elif kind in self.good_counts:
            self.good_counts[kind] += 1
        speed_mult = lerp(SPAWN["start_speed_mult"], SPAWN["end_speed_mult"], diff)
        speed = self.rng.uniform(*config.speed) * speed_mult
        x = self.rng.randint(SPAWN["x_margin"], SCREEN_WIDTH - SPAWN["x_margin"])
        y = self.rng.randint(*SPAWN["spawn_y"])
        return FallingItem(config, self.assets.get(config.asset_key), x, y, speed, self.rng)

    def choose_kind(self, active: list[FallingItem]) -> ItemKind:
        active_curses = sum(1 for item in active if item.config.is_curse)
        moonberries = self.good_counts[ItemKind.MOONBERRY]
        acorns = self.good_counts[ItemKind.ACORN]
        weights = []
        for kind, config in ITEMS.items():
            weight = config.weight
            if config.is_curse:
                if active_curses >= SPAWN["max_curses"] or self.curse_gap > 0:
                    weight = 0.0
            elif kind == ItemKind.MOONBERRY and moonberries < acorns:
                weight += SPAWN["good_balance_bonus"]
            elif kind == ItemKind.ACORN and acorns < moonberries:
                weight += SPAWN["good_balance_bonus"]
            weights.append((kind, weight))
        return weighted_choice(weights, self.rng)


class FoxAI:
    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.target_x = SCREEN_WIDTH * 0.75
        self.reaction_timer = 0.0
        self.patrol_target = AI["patrol_right"]

    def reset(self) -> None:
        self.target_x = SCREEN_WIDTH * 0.75
        self.reaction_timer = 0.0
        self.patrol_target = AI["patrol_right"]

    def update(
        self,
        dt,
        basket: Basket,
        drops: list[FallingItem],
        now,
        pressure: float = 0.0,
    ) -> float:
        """
        Updates the Fox AI movement direction.

        pressure ranges from 0.0 to 1.0:
        - 0.0 = normal Fox behavior
        - 1.0 = urgent Fox behavior when losing or time is low
        """
        if basket.frozen(now):
            return 0.0

        pressure = clamp(pressure, 0.0, 1.0)

        self.reaction_timer -= dt

        if self.reaction_timer <= 0:
            self.target_x = self.choose_target(basket, drops, pressure)

            min_delay, max_delay = AI["reaction_delay"]
            delay_multiplier = lerp(1.0, AI["pressure_reaction_multiplier"], pressure)

            self.reaction_timer = self.rng.uniform(
                min_delay * delay_multiplier,
                max_delay * delay_multiplier,
            )

        if abs(self.target_x - basket.x) <= AI["deadzone"]:
            return 0.0

        return 1.0 if self.target_x > basket.x else -1.0

    def choose_target(self, basket: Basket, drops: list[FallingItem], pressure: float = 0.0) -> float:
        """
        Chooses the Fox target.

        Higher pressure makes the Fox:
        - prioritize acorns more strongly
        - ignore patrol behavior more often
        - make fewer random mistakes
        """
        avoid = self.avoid_curse_target(basket, drops)

        # Even under pressure, the Fox should still avoid nearby curses.
        if avoid is not None:
            return avoid

        best_score = -10_000.0
        best_x = None

        for drop in drops:
            score = self.score_drop(drop, basket, pressure)

            if score > best_score:
                best_score = score
                best_x = drop.x

        mistake_chance = max(
            0.0,
            AI["mistake_chance"] - pressure * AI["pressure_mistake_reduction"],
        )

        if best_x is not None and self.rng.random() > mistake_chance:
            jitter = lerp(AI["jitter_px"], 8, pressure)

            return clamp(
                best_x + self.rng.uniform(-jitter, jitter),
                40,
                SCREEN_WIDTH - 40,
            )

        return self.patrol(basket.x)

    def score_drop(self, drop: FallingItem, basket: Basket, pressure: float = 0.0) -> float:
        """
        Scores each falling object for Fox AI targeting.

        Higher pressure makes acorns more valuable and makes the Fox more willing
        to chase difficult but useful acorns.
        """
        time = drop.time_to_y(basket.y - basket.height * 0.45)

        if time <= 0 or time > 3.2:
            return -400.0

        distance = abs(drop.x - basket.x)
        required_speed = distance / max(0.05, time)
        reachability = 1.0 - clamp(required_speed / max(1.0, basket.speed), 0.0, 1.25)
        urgency = clamp(drop.y / SCREEN_HEIGHT, 0.0, 1.0) * 85

        if drop.kind == ItemKind.ACORN:
            return (
                260
                + pressure * 130
                + urgency
                + reachability * lerp(170, 230, pressure)
                - distance * lerp(0.18, 0.11, pressure)
            )

        if drop.kind == ItemKind.MOONBERRY:
            return (
                -90
                - urgency
                - distance * 0.08
                - pressure * 35
            )

        if drop.kind == ItemKind.MINUS_TWO:
            return (
                -320
                - urgency
                - distance * 0.06
            )

        if drop.kind == ItemKind.FREEZE:
            return (
                -280
                - urgency
                - distance * 0.06
            )

        return -200

    def avoid_curse_target(self, basket: Basket, drops: list[FallingItem]) -> Optional[float]:
        dangerous = [
            drop for drop in drops
            if drop.config.is_curse and drop.y >= AI["danger_y"] and abs(drop.x - basket.x) <= AI["avoid_radius"]
        ]
        if not dangerous:
            return None
        closest = max(dangerous, key=lambda drop: drop.y)
        direction = -1 if closest.x >= basket.x else 1
        return clamp(basket.x + direction * 155, 40, SCREEN_WIDTH - 40)

    def patrol(self, current_x) -> float:
        if abs(current_x - self.patrol_target) < 35:
            self.patrol_target = AI["patrol_left"] if self.patrol_target == AI["patrol_right"] else AI["patrol_right"]
        return self.patrol_target


# =============================================================================
# Result and reward sequence
# =============================================================================

class RewardSequence:
    """
    Result and reward sequence for Canopy Cascade.

    Flow:
    - winner image
    - reward select image
    - crossfade to selected reward image
    - hold selected reward image
    - crossfade to complete image
    - finish

    Explorer chooses with 1, 2, or 3.
    Fox chooses automatically in single-player.
    Fox chooses with 1, 2, or 3 in local multiplayer.
    """

    PHASE_WIN_SEQUENCE = "win_sequence"
    PHASE_SELECT = "reward_select"
    PHASE_TO_CLAIMED = "reward_to_claimed"
    PHASE_CLAIMED = "reward_claimed"
    PHASE_COMPLETE = "complete"

    def __init__(
        self,
        winner: str,
        explorer_score: int,
        fox_score: int,
        game_mode: str,
        assets: AssetManager,
        fonts: FontBook,
        rng: random.Random,
    ) -> None:
        self.winner = winner
        self.explorer_score = explorer_score
        self.fox_score = fox_score
        self.game_mode = game_mode
        self.assets = assets
        self.fonts = fonts
        self.rng = rng

        self.phase = self.PHASE_WIN_SEQUENCE
        self.timer = 0.0
        self.transition_timer = 0.0
        self.finished = False

        self.selected_reward_key: Optional[str] = None

        if self.winner == "explorer":
            self.final_winner = "explorer"
            self.winner_key = "explorer_wins"
            self.select_key = "explorer_choose"
            self.reward_keys = EXPLORER_REWARD_KEYS

        elif self.winner == "fox":
            self.final_winner = "fox"
            self.winner_key = "fox_wins"
            self.select_key = "fox_choose"
            self.reward_keys = FOX_REWARD_KEYS

        else:
            self.final_winner = "tie"
            self.winner_key = "tie"
            self.select_key = ""
            self.reward_keys = []

    # -------------------------------------------------------------------------
    # Update and input
    # -------------------------------------------------------------------------

    def update(self, dt) -> None:
        """Updates the current result/reward phase."""
        if self.finished:
            return

        if self.phase == self.PHASE_WIN_SEQUENCE:
            self.timer += dt

            if self.timer >= SEQUENCE["winner_seconds"]:
                if self.final_winner == "tie":
                    self.phase = self.PHASE_COMPLETE
                else:
                    self.phase = self.PHASE_SELECT

                self.timer = 0.0
                self.transition_timer = 0.0

        elif self.phase == self.PHASE_SELECT:
            # Human Explorer waits for 1/2/3.
            # Local multiplayer Fox waits for 1/2/3.
            # Single-player Fox chooses automatically after a short preview.
            if self.final_winner == "fox" and self.game_mode == "single":
                self.timer += dt

                if self.timer >= SEQUENCE["fox_ai_choice_delay"]:
                    self.selected_reward_key = self.choose_fox_reward_ai()
                    self.phase = self.PHASE_TO_CLAIMED
                    self.timer = 0.0
                    self.transition_timer = 0.0

        elif self.phase == self.PHASE_TO_CLAIMED:
            self.transition_timer += dt

            if self.transition_timer >= SEQUENCE["reward_transition_seconds"]:
                self.phase = self.PHASE_CLAIMED
                self.timer = 0.0
                self.transition_timer = 0.0

        elif self.phase == self.PHASE_CLAIMED:
            self.timer += dt

            if self.timer >= SEQUENCE["reward_hold_seconds"]:
                self.phase = self.PHASE_COMPLETE
                self.timer = 0.0
                self.transition_timer = 0.0

        elif self.phase == self.PHASE_COMPLETE:
            self.timer += dt

            if self.timer >= SEQUENCE["complete_hold_seconds"]:
                self.finished = True

    def handle_key(self, key) -> None:
        """Handles reward selection and skip input."""
        if self.finished:
            return

        if self.phase == self.PHASE_WIN_SEQUENCE:
            if key == pygame.K_SPACE:
                if self.final_winner == "tie":
                    self.phase = self.PHASE_COMPLETE
                else:
                    self.phase = self.PHASE_SELECT

                self.timer = 0.0
                self.transition_timer = 0.0
            return

        if self.phase == self.PHASE_SELECT:
            if key == pygame.K_1:
                self.choose_reward_by_index(0)
            elif key == pygame.K_2:
                self.choose_reward_by_index(1)
            elif key == pygame.K_3:
                self.choose_reward_by_index(2)
            return

        if self.phase == self.PHASE_COMPLETE:
            if key == pygame.K_SPACE:
                self.finished = True

    # -------------------------------------------------------------------------
    # Reward choice logic
    # -------------------------------------------------------------------------

    def choose_reward_by_index(self, index: int) -> None:
        """Chooses reward 1, 2, or 3."""
        if index < 0 or index >= len(self.reward_keys):
            return

        self.selected_reward_key = self.reward_keys[index]
        self.phase = self.PHASE_TO_CLAIMED
        self.timer = 0.0
        self.transition_timer = 0.0

    def choose_fox_reward_ai(self) -> str:
        """
        Chooses a Fox reward automatically in single-player.

        Later, this can use main-maze context like portal state, shard count,
        Grove Shift meter, and Fox urgency.
        """
        score_gap = self.fox_score - self.explorer_score

        if self.explorer_score >= self.fox_score - 1:
            return "reward_portal_flicker"

        if score_gap >= 5:
            return "reward_mischief_surge"

        return "reward_shadow_rush"

    # -------------------------------------------------------------------------
    # Screen drawing helpers
    # -------------------------------------------------------------------------

    def draw_fullscreen_image(self, surface, key: str, alpha: int) -> None:
        """Draws a full-screen cinematic image, with fallback if missing."""
        image = self.assets.get_screen(key)

        if image is not None:
            screen_image = image.copy()
            screen_image.set_alpha(alpha)
            surface.blit(screen_image, (0, 0))
            return

        self.draw_fallback(surface, key, alpha)

    def draw_winner_screen(self, surface, alpha: int) -> None:
        self.draw_fullscreen_image(surface, self.winner_key, alpha)

    def draw_reward_select(self, surface, alpha: int) -> None:
        if self.final_winner == "tie":
            self.draw_complete_screen(surface, alpha)
            return

        self.draw_fullscreen_image(surface, self.select_key, alpha)

    def draw_reward_chosen(self, surface, alpha: int) -> None:
        if self.selected_reward_key is None:
            self.draw_reward_select(surface, alpha)
            return

        self.draw_fullscreen_image(surface, self.selected_reward_key, alpha)

    def draw_complete_screen(self, surface, alpha: int) -> None:
        self.draw_fullscreen_image(surface, "complete", alpha)

    # -------------------------------------------------------------------------
    # Main drawing
    # -------------------------------------------------------------------------

    def draw(self, surface) -> None:
        """
        Draws the result and reward sequence using simple cinematic crossfades.
        """
        surface.fill((0, 0, 0))

        if self.phase == self.PHASE_WIN_SEQUENCE:
            self.draw_win_sequence_transition(surface)

        elif self.phase == self.PHASE_SELECT:
            self.draw_reward_select(surface, 255)

        elif self.phase == self.PHASE_TO_CLAIMED:
            self.draw_reward_to_claimed_transition(surface)

        elif self.phase == self.PHASE_CLAIMED:
            self.draw_reward_claimed_to_complete_transition(surface)

        elif self.phase == self.PHASE_COMPLETE:
            self.draw_complete_screen(surface, 255)

    def draw_win_sequence_transition(self, surface) -> None:
        """
        Shows the winner screen with a slower fade-in, then fades into reward select
        near the end.

        This makes the transition from gameplay to winner feel less sudden.
        """
        fade_in_duration = SEQUENCE["winner_fade_in_seconds"]

        winner_progress = self.timer / max(fade_in_duration, 0.001)
        winner_progress = smoothstep(clamp(winner_progress, 0.0, 1.0))

        winner_alpha = int(255 * winner_progress)

        self.draw_winner_screen(surface, winner_alpha)

        fade_start = max(0.0, SEQUENCE["winner_seconds"] - 1.0)

        if self.timer < fade_start:
            return

        progress = (self.timer - fade_start) / 1.0
        progress = smoothstep(clamp(progress, 0.0, 1.0))

        fade_alpha = int(255 * progress)

        if self.final_winner == "tie":
            self.draw_complete_screen(surface, fade_alpha)
        else:
            self.draw_reward_select(surface, fade_alpha)

    def draw_reward_to_claimed_transition(self, surface) -> None:
        """Crossfades from reward select image to chosen reward image."""
        progress = self.transition_timer / max(SEQUENCE["reward_transition_seconds"], 0.001)
        progress = smoothstep(clamp(progress, 0.0, 1.0))

        select_alpha = int(255 * (1.0 - progress))
        chosen_alpha = int(255 * progress)

        self.draw_reward_select(surface, select_alpha)
        self.draw_reward_chosen(surface, chosen_alpha)

    def draw_reward_claimed_to_complete_transition(self, surface) -> None:
        """
        Holds the chosen reward, then fades into the complete screen near the end.
        """
        fade_duration = SEQUENCE["claimed_to_complete_transition_seconds"]
        fade_start = max(0.0, SEQUENCE["reward_hold_seconds"] - fade_duration)

        if self.timer < fade_start:
            self.draw_reward_chosen(surface, 255)
            return

        progress = (self.timer - fade_start) / max(fade_duration, 0.001)
        progress = smoothstep(clamp(progress, 0.0, 1.0))

        chosen_alpha = int(255 * (1.0 - progress))
        complete_alpha = int(255 * progress)

        self.draw_reward_chosen(surface, chosen_alpha)
        self.draw_complete_screen(surface, complete_alpha)

    # -------------------------------------------------------------------------
    # Fallback drawing
    # -------------------------------------------------------------------------

    def draw_fallback(self, surface, key: str, alpha: int) -> None:
        """Fallback screen if a cinematic image is missing."""
        background = self.assets.get("background")
        background_copy = background.copy()
        background_copy.set_alpha(alpha)
        surface.blit(background_copy, (0, 0))

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((3, 8, 10, int(170 * alpha / 255)))
        surface.blit(overlay, (0, 0))

        panel = pygame.Surface((760, 340), pygame.SRCALPHA)
        rect = panel.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))

        border = GOLD
        title = "Canopy Cascade"
        subtitle = ""

        if key == "explorer_wins":
            border = TEAL
            title = "The Explorer Wins!"
            subtitle = f"Explorer {self.explorer_score}  •  Fox {self.fox_score}"

        elif key == "fox_wins":
            border = PURPLE
            title = "The Fox Wins!"
            subtitle = f"Explorer {self.explorer_score}  •  Fox {self.fox_score}"

        elif key == "tie":
            border = GOLD
            title = "The Canopy Falls in Balance"
            subtitle = f"Explorer {self.explorer_score}  •  Fox {self.fox_score}"

        elif key == "explorer_choose":
            border = TEAL
            title = "Choose Your Reward"
            subtitle = "1 Grove Calm   •   2 Lantern Shield   •   3 Fox Banish"

        elif key == "fox_choose":
            border = PURPLE
            title = "Choose Your Reward"
            subtitle = "1 Mischief Surge   •   2 Shadow Rush   •   3 Portal Flicker"

        elif key == "reward_grove_calm":
            border = TEAL
            title = "Grove Calm"
            subtitle = "The Grove settles and delays the next shift."

        elif key == "reward_lantern_shield":
            border = GOLD
            title = "Lantern Shield"
            subtitle = "The Explorer gains one protective shield."

        elif key == "reward_fox_banish":
            border = PURPLE
            title = "Fox Banish"
            subtitle = "The Fox is sent away for a short time."

        elif key == "reward_mischief_surge":
            border = (255, 80, 190)
            title = "Mischief Surge"
            subtitle = "The Grove Shift meter rises faster."

        elif key == "reward_shadow_rush":
            border = (80, 140, 255)
            title = "Shadow Rush"
            subtitle = "The Fox gains a temporary speed boost."

        elif key == "reward_portal_flicker":
            border = (90, 235, 230)
            title = "Portal Flicker"
            subtitle = "The Explorer's escape route becomes unstable."

        elif key == "complete":
            border = GOLD
            title = "Canopy Cascade Complete"
            subtitle = "The starlit canopy settles and you return to the Grove."

        pygame.draw.rect(panel, (8, 20, 18, int(226 * alpha / 255)), panel.get_rect(), border_radius=28)
        pygame.draw.rect(panel, (*border, int(220 * alpha / 255)), panel.get_rect(), 3, border_radius=28)
        surface.blit(panel, rect)

        draw_shadowed_text(
            surface,
            self.fonts.get(46),
            title,
            TEXT_MAIN,
            (SCREEN_WIDTH // 2, rect.top + 92),
            alpha,
            3,
        )

        draw_centered_text(
            surface,
            self.fonts.get(23),
            subtitle,
            border if key != "complete" else TEXT_SOFT,
            (SCREEN_WIDTH // 2, rect.top + 175),
            alpha,
        )

        if key in ("explorer_choose", "fox_choose"):
            draw_centered_text(
                surface,
                self.fonts.get(20),
                "Press 1, 2, or 3",
                TEXT_MAIN,
                (SCREEN_WIDTH // 2, rect.top + 245),
                alpha,
            )

# =============================================================================
# Gameplay round
# =============================================================================


class CanopyRound:
    def __init__(self, game_mode: str, assets: AssetManager, fonts: FontBook, rng: random.Random) -> None:
        self.game_mode = game_mode
        self.assets = assets
        self.fonts = fonts
        self.rng = rng
        self.spawner = SpawnDirector(rng, assets)
        self.ai = FoxAI(rng)
        self.reset(game_mode)

    def reset(self, game_mode: Optional[str] = None) -> None:
        if game_mode is not None:
            self.game_mode = game_mode
        self.explorer = Basket("explorer", self.assets.get("explorer_basket"), SCREEN_WIDTH * 0.25, PLAYER["basket_y"], PLAYER["speed"], TEAL)
        fox_speed = PLAYER["ai_fox_speed"] if self.game_mode == "single" else PLAYER["speed"]
        self.fox = Basket("fox", self.assets.get("fox_basket"), SCREEN_WIDTH * 0.75, PLAYER["basket_y"], fox_speed, PURPLE)
        self.round_timer = ROUND_SECONDS
        self.countdown_timer = COUNTDOWN_SECONDS + COUNTDOWN_GO_SECONDS
        self.explorer_score = 0
        self.fox_score = 0
        self.drops: list[FallingItem] = []
        self.popups: list[FloatingText] = []
        self.particles: list[Particle] = []
        self.shake_timer = 0.0
        self.shake_strength = 0.0
        self.winner = "tie"
        self.end_message = "Both baskets gathered evenly!"
        self.spawner.reset()
        self.ai.reset()

    def update_countdown(self, dt) -> bool:
        self.countdown_timer -= dt
        return self.countdown_timer <= 0

    def update_gameplay(self, dt, keys) -> bool:
        now = pygame.time.get_ticks() / 1000.0
        self.round_timer = max(0.0, self.round_timer - dt)
        self.shake_timer = max(0.0, self.shake_timer - dt)
        elapsed = ROUND_SECONDS - self.round_timer
        self.update_baskets(dt, keys, now)
        self.drops.extend(self.spawner.update(dt, elapsed, self.drops))
        for drop in self.drops:
            drop.update(dt)
        for popup in self.popups:
            popup.update(dt)
        for particle in self.particles:
            particle.update(dt)
        self.handle_collisions(now)
        self.drops = [drop for drop in self.drops if not drop.offscreen()]
        self.popups = [popup for popup in self.popups if popup.alive()]
        self.particles = [particle for particle in self.particles if particle.alive()]
        if self.round_timer <= 0:
            self.finish_round()
            return True
        return False
    
    def get_fox_pressure(self) -> float:
        """
        Returns how urgently the Fox should play.

        This mirrors the adaptive reward-choice idea used by the other mini-games:
        the Fox gets more aggressive when behind or when time is low.
        """
        pressure = 0.0

        score_gap = self.explorer_score - self.fox_score
        time_left = self.round_timer

        if score_gap >= AI["small_deficit_threshold"]:
            pressure += 0.35

        if score_gap >= AI["large_deficit_threshold"]:
            pressure += 0.30

        if time_left <= 12:
            pressure += 0.20

        if time_left <= 6:
            pressure += 0.15

        return clamp(pressure, 0.0, 1.0)

    def update_baskets(self, dt, keys, now) -> None:
        explorer_dir = (1.0 if keys[pygame.K_d] else 0.0) - (1.0 if keys[pygame.K_a] else 0.0)
        self.explorer.update(dt, explorer_dir, now)
        if self.game_mode == "single":
            fox_pressure = self.get_fox_pressure()

            original_speed = self.fox.speed
            self.fox.speed = original_speed + AI["losing_speed_bonus"] * fox_pressure

            if self.round_timer <= 8:
                self.fox.speed += AI["final_seconds_speed_bonus"] * fox_pressure

            fox_dir = self.ai.update(
                dt,
                self.fox,
                self.drops,
                now,
                pressure=fox_pressure,
            )

            self.fox.update(dt, fox_dir, now)
            self.fox.speed = original_speed

        else:
            fox_dir = (1.0 if keys[pygame.K_RIGHT] else 0.0) - (1.0 if keys[pygame.K_LEFT] else 0.0)
            self.fox.update(dt, fox_dir, now)

    def handle_collisions(self, now) -> None:
        explorer_rect = self.explorer.catch_rect()
        fox_rect = self.fox.catch_rect()
        remaining = []
        for drop in self.drops:
            rect = drop.collision_rect()
            explorer_hit = rect.colliderect(explorer_rect)
            fox_hit = rect.colliderect(fox_rect)
            catcher = None
            if explorer_hit and fox_hit:
                catcher = self.explorer if abs(drop.x - self.explorer.x) <= abs(drop.x - self.fox.x) else self.fox
            elif explorer_hit:
                catcher = self.explorer
            elif fox_hit:
                catcher = self.fox
            if catcher is None:
                remaining.append(drop)
            else:
                self.apply_effect(drop, catcher, rect.center, now)
        self.drops = remaining

    def apply_effect(self, drop: FallingItem, catcher: Basket, pos, now) -> None:
        config = drop.config
        catcher.flash_timer = 0.22
        if config.target_owner == catcher.owner:
            self.add_score(catcher.owner, config.score_delta)
            self.popup(config.popup, pos, catcher.color, 30)
            self.spawn_burst(pos, catcher.color, count=14, speed=190)
        elif config.target_owner is not None:
            self.popup("Not yours", pos, TEXT_SOFT, 22, 0.8)
            self.spawn_burst(pos, (220, 230, 235), count=8, speed=120)
        elif drop.kind == ItemKind.MINUS_TWO:
            self.add_score(catcher.owner, config.score_delta)
            self.popup(config.popup, pos, config.popup_color, 32)
            self.spawn_burst(pos, config.popup_color, count=18, speed=210)
            self.add_screen_shake(5.0, 0.18)
        elif drop.kind == ItemKind.FREEZE:
            catcher.freeze(now)
            self.popup(config.popup, pos, config.popup_color, 24, 1.0)
            self.spawn_burst(pos, config.popup_color, count=18, speed=175)
            self.add_screen_shake(4.0, 0.14)
        self.explorer_score = max(0, self.explorer_score)
        self.fox_score = max(0, self.fox_score)

    def add_score(self, owner, delta) -> None:
        if owner == "explorer":
            self.explorer_score += delta
        elif owner == "fox":
            self.fox_score += delta

    def popup(self, text, pos, color, size=28, lifetime=0.9) -> None:
        self.popups.append(FloatingText(text, pos, color, self.fonts.get(size), lifetime))

    def spawn_burst(self, pos, color, count=12, speed=170) -> None:
        for _ in range(count):
            angle = self.rng.uniform(0, math.tau)
            magnitude = self.rng.uniform(speed * 0.35, speed)
            velocity = (math.cos(angle) * magnitude, math.sin(angle) * magnitude)
            radius = self.rng.uniform(2.2, 5.0)
            lifetime = self.rng.uniform(0.35, 0.65)
            self.particles.append(Particle(pos, color, velocity, radius, lifetime))

    def add_screen_shake(self, strength: float, duration: float) -> None:
        self.shake_strength = max(self.shake_strength, strength)
        self.shake_timer = max(self.shake_timer, duration)

    def shake_offset(self) -> tuple[int, int]:
        if self.shake_timer <= 0:
            return (0, 0)
        strength = self.shake_strength * (self.shake_timer / max(0.001, 0.18))
        return (int(self.rng.uniform(-strength, strength)), int(self.rng.uniform(-strength, strength)))

    def finish_round(self) -> None:
        if self.explorer_score > self.fox_score:
            self.winner = "explorer"
            self.end_message = "The Explorer wins the cascade!"
        elif self.fox_score > self.explorer_score:
            self.winner = "fox"
            self.end_message = "The Fox wins the cascade!"
        else:
            self.winner = "tie"
            self.end_message = "Both baskets gathered evenly!"

    def draw_gameplay(self, surface) -> None:
        surface.blit(self.assets.get("background"), (0, 0))
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((6, 12, 10, 58))
        surface.blit(overlay, (0, 0))
        self.draw_floor_glow(surface)
        for drop in self.drops:
            drop.draw(surface)
        for particle in self.particles:
            particle.draw(surface)
        now = pygame.time.get_ticks() / 1000.0
        self.explorer.draw(surface, now)
        self.fox.draw(surface, now)
        for popup in self.popups:
            popup.draw(surface)
        self.draw_hud(surface)
        self.draw_low_time_pulse(surface)

    def draw_floor_glow(self, surface) -> None:
        layer = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        pygame.draw.ellipse(layer, (60, 190, 110, 34), pygame.Rect(120, 604, 310, 78))
        pygame.draw.ellipse(layer, (125, 85, 200, 36), pygame.Rect(610, 604, 300, 78))
        pygame.draw.ellipse(layer, (0, 0, 0, 75), pygame.Rect(96, 635, 830, 80))
        surface.blit(layer, (0, 0))

    def draw_low_time_pulse(self, surface) -> None:
        if self.round_timer > 10.0:
            return
        amount = 1.0 - clamp(self.round_timer / 10.0, 0.0, 1.0)
        pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.012)
        alpha = int((16 + 30 * pulse) * amount)
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((90, 8, 12, alpha))
        surface.blit(overlay, (0, 0))

    def draw_hud(self, surface) -> None:
        top = pygame.Surface((SCREEN_WIDTH, 120), pygame.SRCALPHA)
        explorer_panel = pygame.Rect(28, 12, 220, 82)
        fox_panel = pygame.Rect(SCREEN_WIDTH - 248, 12, 220, 82)
        self.draw_score_panel(top, explorer_panel, TEAL)
        self.draw_score_panel(top, fox_panel, PURPLE)
        surface.blit(top, (0, 0))

        label_font = self.fonts.get(24)
        score_font = self.fonts.get(36)
        draw_shadowed_text(surface, label_font, "Explorer", TEAL, (explorer_panel.centerx, explorer_panel.top + 24), 255, 2)
        draw_shadowed_text(surface, score_font, str(self.explorer_score), TEXT_MAIN, (explorer_panel.centerx, explorer_panel.top + 58), 255, 2)
        draw_shadowed_text(surface, label_font, "Fox", PURPLE, (fox_panel.centerx, fox_panel.top + 24), 255, 2)
        draw_shadowed_text(surface, score_font, str(self.fox_score), TEXT_MAIN, (fox_panel.centerx, fox_panel.top + 58), 255, 2)
        self.draw_timer(surface)

    def draw_score_panel(self, surface, rect, accent) -> None:
        pygame.draw.rect(surface, (8, 18, 17, 112), rect, border_radius=20)
        pygame.draw.rect(surface, (*accent, 125), rect, 2, border_radius=20)

    def draw_timer(self, surface) -> None:
        seconds = max(0, int(math.ceil(self.round_timer)))
        color = RED if seconds <= 10 else TEXT_MAIN
        full = self.assets.images.get("hourglass_full")
        empty = self.assets.images.get("hourglass_empty")
        hourglass = full if int(pygame.time.get_ticks() / 500) % 2 == 0 else empty
        pulse_scale = 1.0
        if seconds <= 10:
            pulse_scale = 1.0 + 0.06 * (0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.012))
        timer_font = self.fonts.get(int(48 * pulse_scale))
        if hourglass is not None:
            hg = hourglass
            surface.blit(hg, hg.get_rect(center=(SCREEN_WIDTH // 2 - 54, 47)))
            draw_shadowed_text(surface, timer_font, str(seconds), color, (SCREEN_WIDTH // 2 + 20, 49), 255, 2)
        else:
            draw_shadowed_text(surface, self.fonts.get(24), "TIME", TEXT_SOFT, (SCREEN_WIDTH // 2, 30), 255, 2)
            draw_shadowed_text(surface, timer_font, str(seconds), color, (SCREEN_WIDTH // 2, 64), 255, 2)

    def draw_countdown(self, surface) -> None:
        self.draw_gameplay(surface)
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((3, 8, 11, 150))
        surface.blit(overlay, (0, 0))
        if self.countdown_timer > COUNTDOWN_GO_SECONDS:
            number = math.ceil(self.countdown_timer - COUNTDOWN_GO_SECONDS)
            text = str(int(number))
            color = TEXT_MAIN
        else:
            text = "GO!"
            color = GOLD
        pulse = 1.0 + 0.08 * math.sin(pygame.time.get_ticks() * 0.02)
        draw_shadowed_text(surface, self.fonts.get(int(140 * pulse)), text, color, (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 10), 255, 4)
        draw_centered_text(surface, self.fonts.get(25), "Catch your magic before time runs out.", TEXT_SOFT, (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 82), 230)


# =============================================================================
# Embedded mini-game controller
# =============================================================================

class CanopyCascade:
    """
    Integration wrapper for Canopy Cascade.

    game.py should create this class, then call:
    - handle_event(event)
    - update()
    - draw(screen)
    - is_complete()
    - get_selected_reward()
    - get_final_winner()

    This wrapper does not open its own Pygame window.
    """

    def __init__(self, game_mode=DEFAULT_GAME_MODE):
        self.fonts = FontBook()
        self.assets = AssetManager(self.fonts)
        self.rng = random.Random()

        self.state = GameState.TRANSITION
        self.game_mode = self.normalize_game_mode(game_mode)

        self.intro = IntroScene(self.assets, self.fonts)
        self.instructions = InstructionScreen(self.assets, self.fonts)
        self.round = CanopyRound(self.game_mode, self.assets, self.fonts, self.rng)

        self.result_sequence: Optional[RewardSequence] = None
        self.result_pause_timer = 0.0

        self.finished = False

    def normalize_game_mode(self, game_mode: str) -> str:
        """Converts main-game mode names into Canopy Cascade's internal names."""
        if game_mode in ("single", "single_player"):
            return "single"

        return "multi"

    def handle_event(self, event) -> None:
        """Routes keyboard input into the active Canopy Cascade state."""
        if event.type != pygame.KEYDOWN:
            return

        self.handle_key(event.key)

    def handle_key(self, key) -> None:
        advance = key == pygame.K_SPACE

        if self.state == GameState.TRANSITION and advance:
            if not self.intro.is_complete():
                self.intro.skip()
            else:
                self.change_state(GameState.INSTRUCTIONS)

        elif self.state == GameState.INSTRUCTIONS:
            if advance:
                self.round.reset(self.game_mode)
                self.change_state(GameState.COUNTDOWN)

        elif self.state == GameState.RESULT:
            if self.result_sequence is not None:
                self.result_sequence.handle_key(key)

    def change_state(self, state: GameState) -> None:
        self.state = state

        if state == GameState.INSTRUCTIONS:
            self.instructions.reset()

    def update(self) -> None:
        dt = 1 / FPS
        keys = pygame.key.get_pressed()

        if self.state == GameState.TRANSITION:
            self.intro.update(dt)

        elif self.state == GameState.INSTRUCTIONS:
            self.instructions.update(dt)

        elif self.state == GameState.COUNTDOWN:
            if self.round.update_countdown(dt):
                self.change_state(GameState.GAMEPLAY)

        elif self.state == GameState.GAMEPLAY:
            round_finished = self.round.update_gameplay(dt, keys)

            if round_finished:
                self.result_pause_timer = RESULT_PAUSE_SECONDS
                self.change_state(GameState.RESULT_PAUSE)

        elif self.state == GameState.RESULT_PAUSE:
            self.result_pause_timer -= dt

            if self.result_pause_timer <= 0:
                self.result_sequence = RewardSequence(
                    self.round.winner,
                    self.round.explorer_score,
                    self.round.fox_score,
                    self.game_mode,
                    self.assets,
                    self.fonts,
                    self.rng,
                )

                self.change_state(GameState.RESULT)

        elif self.state == GameState.RESULT:
            if self.result_sequence is not None:
                self.result_sequence.update(dt)

                if self.result_sequence.finished:
                    self.change_state(GameState.DONE)

        elif self.state == GameState.DONE:
            self.finished = True

    def draw(self, screen) -> None:
        """Draws the current Canopy Cascade screen."""
        if self.state == GameState.TRANSITION:
            self.intro.draw(screen)

        elif self.state == GameState.INSTRUCTIONS:
            self.instructions.draw(screen, self.game_mode)

        elif self.state == GameState.COUNTDOWN:
            self.round.draw_countdown(screen)

        elif self.state == GameState.GAMEPLAY:
            self.round.draw_gameplay(screen)

        elif self.state == GameState.RESULT_PAUSE:
            self.round.draw_gameplay(screen)

            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 55))
            screen.blit(overlay, (0, 0))

            draw_centered_text(
                screen,
                self.fonts.get(28),
                "The cascade settles...",
                TEXT_SOFT,
                (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2),
                210,
            )

        elif self.state == GameState.RESULT and self.result_sequence is not None:
            self.result_sequence.draw(screen)

    def is_complete(self) -> bool:
        """Returns True once the mini-game has finished and can return to game.py."""
        return self.finished

    def get_selected_reward(self):
        """Returns the selected reward ID in the format game.py already understands."""
        if self.result_sequence is None:
            return None

        reward_key = self.result_sequence.selected_reward_key

        if reward_key is None:
            return None

        return REWARD_KEY_TO_GAME_ID.get(reward_key)

    def get_final_winner(self):
        """Returns the final round winner for optional main-game context."""
        return self.round.winner

class CanopyCascadeApp:
    """Standalone demo runner for Canopy Cascade.

    The main game uses CanopyCascade directly. This app wrapper exists so the
    mini-game can still be launched by itself for demonstration and playtesting.
    """

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Canopy Cascade")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.fonts = FontBook()
        self.assets = AssetManager(self.fonts)
        self.rng = random.Random()
        self.state = GameState.TRANSITION
        self.game_mode = DEFAULT_GAME_MODE
        self.running = True
        self.intro = IntroScene(self.assets, self.fonts)
        self.instructions = InstructionScreen(self.assets, self.fonts)
        self.round = CanopyRound(self.game_mode, self.assets, self.fonts, self.rng)
        self.result_sequence: Optional[RewardSequence] = None
        self.result_pause_timer = 0.0

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            keys = pygame.key.get_pressed()
            self.handle_events()
            self.update(dt, keys)
            self.draw()
            pygame.display.flip()
        pygame.quit()

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.handle_key(event.key)

    def handle_key(self, key) -> None:
        if key == pygame.K_ESCAPE:
            self.running = False
            return
        advance = key == pygame.K_SPACE

        if self.state == GameState.TRANSITION and advance:
            if not self.intro.is_complete():
                self.intro.skip()
            else:
                self.change_state(GameState.INSTRUCTIONS)

        elif self.state == GameState.INSTRUCTIONS:
            if advance:
                self.round.reset(self.game_mode)
                self.change_state(GameState.COUNTDOWN)

        elif self.state == GameState.RESULT:
            if self.result_sequence is not None:
                self.result_sequence.handle_key(key)

    def change_state(self, state: GameState) -> None:
        self.state = state
        if state == GameState.INSTRUCTIONS:
            self.instructions.reset()

    def update(self, dt, keys) -> None:
        if self.state == GameState.TRANSITION:
            self.intro.update(dt)

        elif self.state == GameState.INSTRUCTIONS:
            self.instructions.update(dt)

        elif self.state == GameState.COUNTDOWN:
            if self.round.update_countdown(dt):
                self.change_state(GameState.GAMEPLAY)

        elif self.state == GameState.GAMEPLAY:
            round_finished = self.round.update_gameplay(dt, keys)

            if round_finished:
                self.result_pause_timer = RESULT_PAUSE_SECONDS
                self.change_state(GameState.RESULT_PAUSE)

        elif self.state == GameState.RESULT_PAUSE:
            self.result_pause_timer -= dt

            if self.result_pause_timer <= 0:
                self.result_sequence = RewardSequence(
                    self.round.winner,
                    self.round.explorer_score,
                    self.round.fox_score,
                    self.game_mode,
                    self.assets,
                    self.fonts,
                    self.rng,
                )

                self.change_state(GameState.RESULT)

        elif self.state == GameState.RESULT:
            if self.result_sequence is not None:
                self.result_sequence.update(dt)

                if self.result_sequence.finished:
                    self.change_state(GameState.DONE)

        elif self.state == GameState.DONE:
            self.running = False

    def draw(self) -> None:
        if self.state == GameState.TRANSITION:
            self.intro.draw(self.screen)
        elif self.state == GameState.INSTRUCTIONS:
            self.instructions.draw(self.screen, self.game_mode)
        elif self.state == GameState.COUNTDOWN:
            self.draw_round_with_shake(countdown=True)
        elif self.state == GameState.GAMEPLAY:
            self.draw_round_with_shake(countdown=False)

        elif self.state == GameState.RESULT_PAUSE:
            self.draw_result_pause()

        elif self.state == GameState.RESULT and self.result_sequence is not None:
            self.result_sequence.draw(self.screen)
    
    def draw_result_pause(self) -> None:
        """
        Freezes the final gameplay moment before showing the winner screen.
        This makes the round ending feel intentional instead of sudden.
        """
        self.round.draw_gameplay(self.screen)

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 55))
        self.screen.blit(overlay, (0, 0))

        draw_centered_text(
            self.screen,
            self.fonts.get(28),
            "The cascade settles...",
            TEXT_SOFT,
            (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2),
            210,
        )

    def draw_round_with_shake(self, countdown: bool) -> None:
        temp = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        if countdown:
            self.round.draw_countdown(temp)
        else:
            self.round.draw_gameplay(temp)
        offset = self.round.shake_offset()
        self.screen.fill((0, 0, 0))
        self.screen.blit(temp, offset)


def main() -> None:
    """Runs Canopy Cascade as a standalone demo."""
    CanopyCascadeApp().run()


if __name__ == "__main__":
    main()