"""
starlight_crossing.py

Starlight Crossing mini-game for The Shifting Grove.

This module implements a circuit-rotation puzzle that can run inside the main
maze game or as a standalone demo. The Explorer and Fox solve separate 4x4
starlight boards by rotating path tiles to connect each source to its goal. The
winner chooses a reward that is returned to game.py, where the main maze applies
the reward effect.

This file owns Starlight Crossing's internal systems:
- intro, instruction, fade, and countdown flow
- guaranteed-solvable board generation
- tile rotation and connection validation
- Explorer and Fox input handling
- heuristic Fox AI in single-player mode
- timed round resolution
- reward selection and completion state

game.py is responsible for starting this mini-game, updating/drawing it while
the maze is paused, and applying the selected reward after completion.
"""

import math
import random
from collections import deque

import pygame


# ------------------------------------------------------------
# Settings
# ------------------------------------------------------------

SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
FPS = 60

TRIGGER_SYMBOL_PATH = "assets/images/starlight_circuit_trigger.png"
INSTRUCTION_BACKGROUND_PATH = "assets/images/starlight_crossing_instructions_bg.png"
GAME_BACKGROUND_PATH = "assets/images/starlight_crossing_game_bg.png"
HOURGLASS_FULL_PATH = "assets/images/hourglass_full.png"
HOURGLASS_EMPTY_PATH = "assets/images/hourglass_empty.png"

FANTASY_FONT_PATH = "assets/fonts/fantasy_font.ttf"

# Reward images
STARLIGHT_REWARD_EXPLORER_SELECT_PATH = "assets/images/starlight_reward_explorer_select.png"
STARLIGHT_REWARD_FOX_SELECT_PATH = "assets/images/starlight_reward_fox_select.png"

STARLIGHT_REWARD_GROVE_CALM_PATH = "assets/images/starlight_reward_grove_calm.png"
STARLIGHT_REWARD_LANTERN_SHIELD_PATH = "assets/images/starlight_reward_lantern_shield.png"
STARLIGHT_REWARD_FOX_BANISH_PATH = "assets/images/starlight_reward_fox_banish.png"

STARLIGHT_REWARD_MISCHIEF_SURGE_PATH = "assets/images/starlight_reward_mischief_surge.png"
STARLIGHT_REWARD_SHADOW_RUSH_PATH = "assets/images/starlight_reward_shadow_rush.png"
STARLIGHT_REWARD_PORTAL_FLICKER_PATH = "assets/images/starlight_reward_portal_flicker.png"

STARLIGHT_CROSSING_COMPLETE_PATH = "assets/images/starlight_crossing_complete.png"

BG_COLOR = (5, 16, 18)

WHITE = (245, 242, 232)
MUTED_WHITE = (222, 228, 220)
SOFT_GOLD = (226, 192, 116)
DARK_TEXT_SHADOW = (5, 8, 12)

TEAL_1 = (120, 255, 220)
TEAL_2 = (70, 235, 210)

PURPLE_1 = (215, 120, 255)
PURPLE_2 = (180, 95, 255)

# Gameplay grid layout
GRID_SIZE = 4

# This first working version draws the tile paths in code instead of using
# exported tile PNGs. That guarantees the visual openings match the logic.
TILE_SIZE = 92
TILE_GAP = 0
BOARD_PIXEL_SIZE = GRID_SIZE * TILE_SIZE + (GRID_SIZE - 1) * TILE_GAP

# Symmetrical layout for two larger readable 4x4 boards.
EXPLORER_GRID_X = 82
FOX_GRID_X = SCREEN_WIDTH - 82 - BOARD_PIXEL_SIZE
GRID_Y = 260


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------

def load_image(path):
    """Safely loads an image and returns None if the file is missing."""
    try:
        return pygame.image.load(path).convert_alpha()
    except (pygame.error, FileNotFoundError):
        print(f"Warning: could not load image: {path}")
        return None


def load_font(path, size, fallback_name="georgia", bold=False):
    """Safely loads the fantasy font or falls back to a system font."""
    try:
        return pygame.font.Font(path, size)
    except (pygame.error, FileNotFoundError):
        print(f"Warning: could not load font: {path}")
        return pygame.font.SysFont(fallback_name, size, bold=bold)


def scale_preserve_ratio(image, max_w, max_h):
    """Scales an image without squishing it."""
    w, h = image.get_size()
    scale = min(max_w / w, max_h / h)
    return pygame.transform.smoothscale(image, (int(w * scale), int(h * scale)))


def lerp(a, b, t):
    return a + (b - a) * t


def ease_out_quad(t):
    return 1 - (1 - t) * (1 - t)


def ease_in_out(t):
    return 3 * t * t - 2 * t * t * t


def draw_soft_glow(surface, center, radius, color, alpha):
    """Draws a soft circular glow."""
    glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)

    for r in range(radius, 0, -6):
        layer_alpha = int(alpha * (r / radius) * 0.2)
        pygame.draw.circle(glow, (*color, layer_alpha), (radius, radius), r)

    surface.blit(glow, (center[0] - radius, center[1] - radius))


def draw_translucent_panel(
    surface,
    rect,
    fill_color=(8, 12, 22, 172),
    border_color=(226, 192, 116, 220),
    border_width=3,
    radius=26,
    shadow_offset=7,
):
    """Draws a soft rounded translucent panel."""
    shadow_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(
        shadow_surface,
        (0, 0, 0, 75),
        shadow_surface.get_rect(),
        border_radius=radius,
    )
    surface.blit(shadow_surface, (rect.x + shadow_offset, rect.y + shadow_offset))

    panel_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)

    pygame.draw.rect(
        panel_surface,
        fill_color,
        panel_surface.get_rect(),
        border_radius=radius,
    )

    pygame.draw.rect(
        panel_surface,
        border_color,
        panel_surface.get_rect(),
        width=border_width,
        border_radius=radius,
    )

    inner_rect = pygame.Rect(8, 8, rect.width - 16, rect.height - 16)
    pygame.draw.rect(
        panel_surface,
        (255, 245, 205, 45),
        inner_rect,
        width=1,
        border_radius=max(8, radius - 8),
    )

    surface.blit(panel_surface, rect.topleft)


def draw_text_center(surface, text, font, color, center, alpha=255, shadow=True):
    """Draws centered text with subtle shadow."""
    alpha = max(0, min(255, alpha))

    if shadow:
        shadow_surf = font.render(text, True, DARK_TEXT_SHADOW).convert_alpha()
        shadow_surf.set_alpha(int(alpha * 0.7))
        shadow_rect = shadow_surf.get_rect(center=(center[0] + 2, center[1] + 2))
        surface.blit(shadow_surf, shadow_rect)

    text_surf = font.render(text, True, color).convert_alpha()
    text_surf.set_alpha(alpha)
    rect = text_surf.get_rect(center=center)
    surface.blit(text_surf, rect)


def draw_text_left(surface, text, font, color, x, y, alpha=255, shadow=True):
    """Draws left-aligned text with small shadow."""
    alpha = max(0, min(255, alpha))

    if shadow:
        shadow_surf = font.render(text, True, DARK_TEXT_SHADOW).convert_alpha()
        shadow_surf.set_alpha(int(alpha * 0.75))
        surface.blit(shadow_surf, (x + 2, y + 2))

    text_surf = font.render(text, True, color).convert_alpha()
    text_surf.set_alpha(alpha)
    surface.blit(text_surf, (x, y))


def draw_wrapped_text(surface, text, font, color, x, y, max_width, line_spacing=7, alpha=255):
    """Draws wrapped text and returns next y-position."""
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        test_surface = font.render(test_line, True, color)

        if test_surface.get_width() <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    line_height = font.get_height() + line_spacing

    for index, line in enumerate(lines):
        draw_text_left(
            surface,
            line,
            font,
            color,
            x,
            y + index * line_height,
            alpha=alpha,
            shadow=True,
        )

    return y + len(lines) * line_height


def get_cell_rect(grid_x, grid_y, row, col):
    """Returns the rectangle for a grid cell."""
    x = grid_x + col * (TILE_SIZE + TILE_GAP)
    y = grid_y + row * (TILE_SIZE + TILE_GAP)
    return pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)


# ------------------------------------------------------------
# Intro + instruction class
# ------------------------------------------------------------

class StarlightCrossingIntro:
    """Controls the intro and instruction screen."""

    def __init__(self):
        self.frame = 0
        self.finished = False
        self.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 10)

        raw_logo = load_image(TRIGGER_SYMBOL_PATH)
        self.logo = scale_preserve_ratio(raw_logo, 170, 170) if raw_logo else None

        raw_instruction_bg = load_image(INSTRUCTION_BACKGROUND_PATH)
        self.instruction_bg = (
            pygame.transform.smoothscale(raw_instruction_bg, (SCREEN_WIDTH, SCREEN_HEIGHT))
            if raw_instruction_bg else None
        )

        self.snakes = self.create_snakes()
        self.sparks = []

        self.title_font = load_font(FANTASY_FONT_PATH, 58, bold=True)
        self.subtitle_font = load_font(FANTASY_FONT_PATH, 22)

        self.how_to_font = load_font(FANTASY_FONT_PATH, 44, bold=True)
        self.section_font = load_font(FANTASY_FONT_PATH, 21, bold=True)
        self.bullet_font = load_font(FANTASY_FONT_PATH, 15)
        self.footer_font = load_font(FANTASY_FONT_PATH, 17, bold=True)

    def create_snakes(self):
        """Creates dotted starlight snakes from all sides."""
        starts = [
            (-80, 120), (-80, 280), (-80, 520),
            (SCREEN_WIDTH + 80, 140), (SCREEN_WIDTH + 80, 320), (SCREEN_WIDTH + 80, 560),
            (160, -80), (500, -80), (860, -80),
            (150, SCREEN_HEIGHT + 80), (520, SCREEN_HEIGHT + 80), (860, SCREEN_HEIGHT + 80),
            (-60, -60), (SCREEN_WIDTH + 60, -60),
            (-60, SCREEN_HEIGHT + 60), (SCREEN_WIDTH + 60, SCREEN_HEIGHT + 60),
        ]

        snakes = []

        for i, start in enumerate(starts):
            color = (
                random.choice([TEAL_1, TEAL_2])
                if i % 2 == 0
                else random.choice([PURPLE_1, PURPLE_2])
            )

            snakes.append({
                "start": start,
                "color": color,
                "delay": i * 4,
                "length": random.randint(16, 22),
                "head_size": random.randint(7, 10),
                "spiral_dir": 1 if i % 2 == 0 else -1,
                "angle_offset": random.uniform(0, math.tau),
            })

        return snakes

    def create_burst(self):
        """Creates spark burst."""
        self.sparks.clear()

        for _ in range(130):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(1.8, 6.0)
            color = random.choice([WHITE, SOFT_GOLD, TEAL_1, TEAL_2, PURPLE_1, PURPLE_2])

            self.sparks.append({
                "angle": angle,
                "speed": speed,
                "life": random.randint(30, 55),
                "size": random.randint(2, 5),
                "color": color,
                "age": 0,
            })

    def update(self):
        self.frame += 1

        if self.frame == 210:
            self.create_burst()

        if self.frame > 540:
            self.finished = True

        for spark in self.sparks:
            spark["age"] += 1

    def draw(self, screen):
        self.draw_background(screen)
        self.draw_snakes(screen)
        self.draw_center_burst(screen)
        self.draw_logo(screen)
        self.draw_title(screen)
        self.draw_instruction_fade(screen)

    def draw_background(self, screen):
        screen.fill(BG_COLOR)

        background_random = random.Random(4)

        for _ in range(120):
            x = background_random.randint(0, SCREEN_WIDTH)
            y = background_random.randint(0, SCREEN_HEIGHT)
            color = background_random.choice([WHITE, TEAL_1, PURPLE_1])
            alpha = background_random.randint(25, 80)

            dot = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(dot, (*color, alpha), (2, 2), background_random.randint(1, 2))
            screen.blit(dot, (x, y))

    def snake_head_position(self, snake, local_frame):
        if local_frame < 0:
            return snake["start"]

        if local_frame <= 150:
            t = ease_out_quad(local_frame / 150)

            sx, sy = snake["start"]
            cx, cy = self.center

            mid_pull = 0.22 * math.sin(t * math.pi)

            x = lerp(sx, cx, t) + (cy - sy) * mid_pull * 0.18
            y = lerp(sy, cy, t) + (sx - cx) * mid_pull * 0.18

            return (x, y)

        spiral_frame = min(local_frame - 150, 70)
        t = ease_in_out(spiral_frame / 70)

        turns = 2.0
        angle = snake["angle_offset"] + snake["spiral_dir"] * (turns * math.tau * t)

        start_radius = 85
        end_radius = 14
        radius = lerp(start_radius, end_radius, t)

        x = self.center[0] + math.cos(angle) * radius
        y = self.center[1] + math.sin(angle) * radius

        return (x, y)

    def draw_snakes(self, screen):
        if self.frame > 235:
            return

        for snake in self.snakes:
            local_frame = self.frame - snake["delay"]

            if local_frame < 0:
                continue

            for i in range(snake["length"]):
                trail_t = i / snake["length"]
                sample_frame = local_frame - i * 3

                if sample_frame < 0:
                    continue

                px, py = self.snake_head_position(snake, sample_frame)

                size = max(2, int(snake["head_size"] * (1 - trail_t * 0.7)))
                alpha = max(20, int(255 * (1 - trail_t)))

                particle = pygame.Surface((size * 6, size * 6), pygame.SRCALPHA)
                pygame.draw.circle(
                    particle,
                    (*snake["color"], alpha),
                    (size * 3, size * 3),
                    size,
                )

                screen.blit(particle, (px - size * 3, py - size * 3))

            hx, hy = self.snake_head_position(snake, local_frame)
            draw_soft_glow(screen, (int(hx), int(hy)), 28, snake["color"], 110)
            pygame.draw.circle(screen, WHITE, (int(hx), int(hy)), 3)

    def draw_center_burst(self, screen):
        if self.frame < 210:
            return

        for spark in self.sparks:
            if spark["age"] > spark["life"]:
                continue

            t = spark["age"] / spark["life"]
            dist = spark["speed"] * spark["age"]

            x = self.center[0] + math.cos(spark["angle"]) * dist
            y = self.center[1] + math.sin(spark["angle"]) * dist

            alpha = int(255 * (1 - t))
            size = max(1, int(spark["size"] * (1 - t * 0.5)))

            particle = pygame.Surface((size * 8, size * 8), pygame.SRCALPHA)
            pygame.draw.circle(
                particle,
                (*spark["color"], alpha),
                (size * 4, size * 4),
                size,
            )

            screen.blit(particle, (x - size * 4, y - size * 4))

    def draw_logo(self, screen):
        if self.frame < 235:
            return

        fade_in = min((self.frame - 235) / 65, 1.0)
        fade_out = 1.0

        if self.frame > 370:
            fade_out = max(0.0, 1.0 - (self.frame - 370) / 80)

        alpha = int(255 * fade_in * fade_out)
        smooth_t = ease_out_quad(fade_in)

        logo_y = lerp(self.center[1] + 18, self.center[1] - 70, smooth_t)
        logo_center = (self.center[0], int(logo_y))

        draw_soft_glow(screen, logo_center, 90, SOFT_GOLD, int(120 * fade_in * fade_out))
        draw_soft_glow(screen, logo_center, 65, WHITE, int(70 * fade_in * fade_out))

        if self.logo:
            base_w, base_h = self.logo.get_size()
            scale = 0.72 + 0.28 * smooth_t

            scaled = pygame.transform.smoothscale(
                self.logo,
                (int(base_w * scale), int(base_h * scale)),
            )

            scaled.set_alpha(alpha)
            rect = scaled.get_rect(center=logo_center)
            screen.blit(scaled, rect)
        else:
            pygame.draw.circle(screen, SOFT_GOLD, logo_center, int(40 + 30 * fade_in), 4)

    def draw_title(self, screen):
        if self.frame < 285:
            return

        fade_in = min((self.frame - 285) / 65, 1.0)
        fade_out = 1.0

        if self.frame > 370:
            fade_out = max(0.0, 1.0 - (self.frame - 370) / 75)

        alpha = int(255 * fade_in * fade_out)
        smooth_t = ease_out_quad(fade_in)

        title_y = lerp(560, 455, smooth_t)
        subtitle_y = lerp(610, 510, smooth_t)

        draw_text_center(
            screen,
            "Starlight Crossing",
            self.title_font,
            SOFT_GOLD,
            (SCREEN_WIDTH // 2, int(title_y)),
            alpha=alpha,
        )

        draw_text_center(
            screen,
            "Paths awaken beneath the Grove",
            self.subtitle_font,
            WHITE,
            (SCREEN_WIDTH // 2, int(subtitle_y)),
            alpha=alpha,
        )

    def draw_instruction_fade(self, screen):
        if self.frame < 365:
            return

        bg_t = min((self.frame - 365) / 90, 1.0)
        bg_alpha = int(255 * bg_t)

        layer = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

        if self.instruction_bg:
            bg = self.instruction_bg.copy()
            bg.set_alpha(bg_alpha)
            layer.blit(bg, (0, 0))
        else:
            layer.fill((12, 24, 24, bg_alpha))

        veil = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        veil.fill((0, 0, 0, int(45 * bg_t)))
        layer.blit(veil, (0, 0))

        text_t = 0.0
        if self.frame > 430:
            text_t = min((self.frame - 430) / 80, 1.0)

        text_alpha = int(255 * text_t)

        if text_alpha > 0:
            self.draw_instructions(layer, text_alpha)

        screen.blit(layer, (0, 0))

    def draw_rune_divider(self, surface, x, y, width, color, alpha):
        alpha = max(0, min(255, alpha))

        line_surface = pygame.Surface((width, 24), pygame.SRCALPHA)

        pygame.draw.line(
            line_surface,
            (*color, int(alpha * 0.75)),
            (0, 12),
            (width, 12),
            2,
        )

        pygame.draw.circle(line_surface, (*SOFT_GOLD, int(alpha * 0.95)), (width // 2, 12), 4)
        pygame.draw.circle(line_surface, (*color, int(alpha * 0.75)), (width // 2, 12), 10, 1)

        surface.blit(line_surface, (x, y))

    def draw_bullet(self, surface, x, y, color, alpha):
        alpha = max(0, min(255, alpha))

        draw_soft_glow(surface, (x, y), 10, color, int(alpha * 0.45))
        pygame.draw.circle(surface, (*SOFT_GOLD, alpha), (x, y), 4)
        pygame.draw.circle(surface, (*color, alpha), (x, y), 2)

    def draw_instructions(self, surface, alpha):
        title_color = SOFT_GOLD
        goal_color = TEAL_1
        controls_color = PURPLE_1
        body_color = WHITE

        draw_text_center(
            surface,
            "HOW TO PLAY",
            self.how_to_font,
            title_color,
            (SCREEN_WIDTH // 2, 118),
            alpha=alpha,
        )

        panel_rect = pygame.Rect(245, 178, 535, 455)
        draw_translucent_panel(
            surface,
            panel_rect,
            fill_color=(8, 12, 22, int(172 * alpha / 255)),
            border_color=(226, 192, 116, int(220 * alpha / 255)),
            border_width=3,
            radius=26,
            shadow_offset=7,
        )

        left_x = panel_rect.x + 42
        text_x = left_x + 42
        max_width = panel_rect.width - 90
        y = panel_rect.y + 34

        draw_text_left(surface, "GOALS", self.section_font, goal_color, left_x, y, alpha=alpha)
        self.draw_rune_divider(surface, left_x, y + 27, 190, goal_color, alpha)
        y += 64

        goal_lines = [
            "Connect starlight from the source tile to the goal tile.",
            "The first side to complete its crossing wins.",
            "If time runs out, the side closest to the true path wins.",
        ]

        for line in goal_lines:
            self.draw_bullet(surface, left_x + 9, y + 15, goal_color, alpha)

            y = draw_wrapped_text(
                surface,
                line,
                self.bullet_font,
                body_color,
                text_x,
                y,
                max_width,
                line_spacing=5,
                alpha=alpha,
            )

            y += 15

        y += 2

        draw_text_left(surface, "CONTROLS", self.section_font, controls_color, left_x, y, alpha=alpha)
        self.draw_rune_divider(surface, left_x, y + 27, 220, controls_color, alpha)
        y += 64

        control_lines = [
            "Explorer: WASD to move, SPACE to rotate.",
            "Local multiplayer: Arrow keys + ENTER control Fox.",
        ]

        for line in control_lines:
            self.draw_bullet(surface, left_x + 9, y + 15, controls_color, alpha)

            y = draw_wrapped_text(
                surface,
                line,
                self.bullet_font,
                body_color,
                text_x,
                y,
                max_width,
                line_spacing=5,
                alpha=alpha,
            )

            y += 15

        draw_text_center(
            surface,
            "PRESS SPACE TO BEGIN",
            self.footer_font,
            title_color,
            (SCREEN_WIDTH // 2, 690),
            alpha=alpha,
        )

# ------------------------------------------------------------
# Gameplay grid class
# ------------------------------------------------------------

# Direction constants used by the path logic.
UP = 0
RIGHT = 1
DOWN = 2
LEFT = 3

DIRECTION_VECTORS = {
    UP: (-1, 0),
    RIGHT: (0, 1),
    DOWN: (1, 0),
    LEFT: (0, -1),
}

OPPOSITE_DIRECTION = {
    UP: DOWN,
    RIGHT: LEFT,
    DOWN: UP,
    LEFT: RIGHT,
}

# Base orientations before rotation:
# straight = vertical, corner = up/right, source = exits right, goal = accepts left.
BASE_TILE_CONNECTIONS = {
    "straight": {UP, DOWN},
    "corner": {UP, RIGHT},
    "source": {RIGHT},
    "goal": {LEFT},
}

ROTATABLE_TILE_TYPES = {"straight", "corner"}

# Gameplay modes passed in by game.py or the standalone demo launcher.
MODE_SINGLE_PLAYER = "single_player"
MODE_LOCAL_MULTIPLAYER = "local_multiplayer"

# Difficulty presets control board generation and Fox AI pacing together.
DIFFICULTY_EASY = "easy"
DIFFICULTY_MEDIUM = "medium"
DIFFICULTY_MEDIUM_HARD = "medium_hard"
DIFFICULTY_HARD = "hard"
DEFAULT_DIFFICULTY = DIFFICULTY_MEDIUM_HARD

DIFFICULTY_SETTINGS = {
    DIFFICULTY_EASY: {
        "path_length_range": (6, 8),
        "rotation_cost_range": (4, 7),
        "max_starting_connected_tiles": 3,
        "fox_ai_move_interval": 160,
        "fox_ai_think_skip_chance": 0.18,
        "fox_ai_random_noise": 0.55,
    },
    DIFFICULTY_MEDIUM: {
        "path_length_range": (7, 10),
        "rotation_cost_range": (7, 10),
        "max_starting_connected_tiles": 2,
        "fox_ai_move_interval": 130,
        "fox_ai_think_skip_chance": 0.12,
        "fox_ai_random_noise": 0.45,
    },
    DIFFICULTY_MEDIUM_HARD: {
        "path_length_range": (8, 12),
        "rotation_cost_range": (10, 14),
        "max_starting_connected_tiles": 2,
        "fox_ai_move_interval": 78,
        "fox_ai_think_skip_chance": 0.02,
        "fox_ai_random_noise": 0.08,
    },
    DIFFICULTY_HARD: {
        "path_length_range": (10, 13),
        "rotation_cost_range": (12, 16),
        "max_starting_connected_tiles": 1,
        "fox_ai_move_interval": 58,
        "fox_ai_think_skip_chance": 0.0,
        "fox_ai_random_noise": 0.03,
    },
}

# ------------------------------------------------------------
# Reward IDs
# ------------------------------------------------------------

WINNER_EXPLORER = "explorer"
WINNER_FOX = "fox"
WINNER_TIE = "tie"

REWARD_GROVE_CALM = "grove_calm"
REWARD_LANTERN_SHIELD = "lantern_shield"
REWARD_FOX_BANISH = "fox_banish"

REWARD_MISCHIEF_SURGE = "mischief_surge"
REWARD_SHADOW_RUSH = "shadow_rush"
REWARD_PORTAL_FLICKER = "portal_flicker"

EXPLORER_REWARDS = [
    {
        "id": REWARD_GROVE_CALM,
        "title": "Grove Calm",
        "description": "Reduce the Grove Shift meter by 15.",
    },
    {
        "id": REWARD_LANTERN_SHIELD,
        "title": "Lantern Shield",
        "description": "Block the fox's next catch.",
    },
    {
        "id": REWARD_FOX_BANISH,
        "title": "Fox Banish",
        "description": "Freeze the fox for 5 seconds.",
    },
]

FOX_REWARDS = [
    {
        "id": REWARD_MISCHIEF_SURGE,
        "title": "Mischief Surge",
        "description": "Increase the Grove Shift meter by 15.",
    },
    {
        "id": REWARD_SHADOW_RUSH,
        "title": "Shadow Rush",
        "description": "Give the fox a speed boost.",
    },
    {
        "id": REWARD_PORTAL_FLICKER,
        "title": "Portal Flicker",
        "description": "Delay the portal for 5 seconds.",
    },
]

REWARD_PHASE_NONE = "none"
REWARD_PHASE_WIN_SEQUENCE = "win_sequence"
REWARD_PHASE_SELECT = "reward_select"
REWARD_PHASE_TO_CLAIMED = "reward_to_claimed"
REWARD_PHASE_CLAIMED = "reward_claimed"
REWARD_PHASE_COMPLETE = "complete"

WIN_SEQUENCE_FRAMES = 120
REWARD_TRANSITION_FRAMES = 60
REWARD_CLAIMED_HOLD_FRAMES = 210
COMPLETE_HOLD_FRAMES = 180
AI_REWARD_PREVIEW_FRAMES = 180

WIN_TO_REWARD_FADE_FRAMES = 50
CLAIMED_TO_COMPLETE_FADE_FRAMES = 60

MAX_BOARD_GENERATION_ATTEMPTS = 500
ROUND_TIME_SECONDS = 90
# Fox AI presentation tuning. These control how the AI looks on-screen after it
# has already chosen a strategic move.
FOX_AI_CURSOR_STEP_INTERVAL = 4
FOX_AI_ROTATE_DELAY = 7
FOX_AI_MIN_MOVE_INTERVAL = 42

STONE_FILL = (24, 32, 31)
STONE_FILL_DARK = (9, 14, 16)
STONE_EDGE = (63, 78, 72)
DIM_TEAL_PATH = (43, 105, 108)
DIM_PURPLE_PATH = (92, 55, 122)
class PathTile:
    """One logical path tile whose drawing is generated directly from its connections."""

    def __init__(self, tile_type, rotation=0, solution_rotation=None):
        self.tile_type = tile_type
        self.rotation = rotation % 4
        self.solution_rotation = solution_rotation

    def rotate(self):
        """Rotates a non-terminal tile clockwise."""
        if self.tile_type not in ROTATABLE_TILE_TYPES:
            return False

        self.rotation = (self.rotation + 1) % 4
        return True

    def get_connections(self):
        """Returns the active openings after rotation."""
        base_connections = BASE_TILE_CONNECTIONS[self.tile_type]
        return {(direction + self.rotation) % 4 for direction in base_connections}

    def copy(self):
        """Returns a copy for AI move simulation."""
        return PathTile(self.tile_type, self.rotation, self.solution_rotation)


class SolvingBoard:
    """
    A guaranteed-solvable 4x4 Starlight Crossing board.

    The board generator creates a hidden valid source-to-goal path, places the
    required tile types along that route, adds decoy/filler pieces elsewhere,
    and scrambles the route into a target difficulty range. Drawing is generated
    from the same connection data used by the solver, so visuals and logic stay
    synchronized.
    """

    def __init__(self, grid_x, grid_y, accent_color, dim_color, title, difficulty=DEFAULT_DIFFICULTY):
        self.grid_x = grid_x
        self.grid_y = grid_y
        self.accent_color = accent_color
        self.dim_color = dim_color
        self.title = title
        self.difficulty = difficulty
        self.settings = DIFFICULTY_SETTINGS[difficulty]

        self.solution_path = []
        self.solution_positions = set()
        self.start = (0, 0)
        self.goal = (GRID_SIZE - 1, GRID_SIZE - 1)
        self.target_rotation_cost = 0
        self.generation_attempts_used = 0
        self.starting_connected_tiles = 0
        self.tiles = []

        self.generate_new_board()

    # ------------------------------------------------------------------
    # Board generation
    # ------------------------------------------------------------------

    def generate_new_board(self):
        """Generates a fresh board that aims for the selected difficulty."""
        best_candidate = None
        best_score = 999999

        for attempt in range(1, MAX_BOARD_GENERATION_ATTEMPTS + 1):
            path = self.generate_random_solution_path()
            tiles = self.create_solved_tiles_from_path(path)
            rotation_cost = self.scramble_tiles_for_difficulty(tiles, path)
            connected_count = self.get_connected_count_on_board(tiles, path[0])
            solved_at_start = self.has_valid_path_on_board(tiles, path[0], path[-1])

            candidate_score = self.score_candidate(rotation_cost, connected_count, solved_at_start)

            if candidate_score < best_score:
                best_candidate = (path, tiles, rotation_cost, connected_count, attempt)
                best_score = candidate_score

            min_cost, max_cost = self.settings["rotation_cost_range"]
            max_starting_connected = self.settings["max_starting_connected_tiles"]

            if (
                min_cost <= rotation_cost <= max_cost
                and connected_count <= max_starting_connected
                and not solved_at_start
            ):
                self.apply_candidate(path, tiles, rotation_cost, connected_count, attempt)
                return

        # Fallback: still generated from a valid hidden solution path, even if it
        # missed one of the ideal difficulty filters.
        path, tiles, rotation_cost, connected_count, attempt = best_candidate
        self.apply_candidate(path, tiles, rotation_cost, connected_count, attempt)

    def score_candidate(self, rotation_cost, connected_count, solved_at_start):
        """Scores how close a generated board is to the target difficulty."""
        min_cost, max_cost = self.settings["rotation_cost_range"]
        max_starting_connected = self.settings["max_starting_connected_tiles"]

        if rotation_cost < min_cost:
            cost_penalty = min_cost - rotation_cost
        elif rotation_cost > max_cost:
            cost_penalty = rotation_cost - max_cost
        else:
            cost_penalty = 0

        connected_penalty = max(0, connected_count - max_starting_connected)
        solved_penalty = 45 if solved_at_start else 0

        return cost_penalty * 10 + connected_penalty * 8 + solved_penalty

    def apply_candidate(self, path, tiles, rotation_cost, connected_count, attempt):
        """Stores a generated board candidate as the active board."""
        self.solution_path = path
        self.solution_positions = set(path)
        self.start = path[0]
        self.goal = path[-1]
        self.tiles = tiles
        self.target_rotation_cost = rotation_cost
        self.starting_connected_tiles = connected_count
        self.generation_attempts_used = attempt

    def generate_random_solution_path(self):
        """Generates a self-avoiding path with variable source and goal cells."""
        border_positions = [
            (row, col)
            for row in range(GRID_SIZE)
            for col in range(GRID_SIZE)
            if row in (0, GRID_SIZE - 1) or col in (0, GRID_SIZE - 1)
        ]

        min_length, max_length = self.settings["path_length_range"]

        for _ in range(300):
            start = random.choice(border_positions)
            target_length = random.randint(min_length, max_length)
            path = self.find_self_avoiding_path(start, target_length, border_positions)

            if path:
                return path

        # Reliable fallback paths if random DFS fails.
        fallback_paths = [
            [(0, 0), (0, 1), (1, 1), (1, 2), (2, 2), (2, 3), (3, 3), (3, 2)],
            [(3, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2), (0, 3), (1, 3)],
            [(0, 3), (0, 2), (1, 2), (1, 1), (2, 1), (2, 0), (3, 0), (3, 1)],
        ]

        return random.choice(fallback_paths)

    def find_self_avoiding_path(self, start, target_length, border_positions):
        """Uses randomized DFS to create one readable source-to-goal path."""
        border_set = set(border_positions)
        path = [start]
        visited = {start}

        def search():
            if len(path) == target_length:
                end = path[-1]
                distance = abs(end[0] - start[0]) + abs(end[1] - start[1])
                return end in border_set and end != start and distance >= 4

            current_row, current_col = path[-1]
            neighbors = []

            for direction in (UP, RIGHT, DOWN, LEFT):
                row_change, col_change = DIRECTION_VECTORS[direction]
                next_position = (current_row + row_change, current_col + col_change)
                next_row, next_col = next_position

                if not (0 <= next_row < GRID_SIZE and 0 <= next_col < GRID_SIZE):
                    continue

                if next_position in visited:
                    continue

                neighbors.append(next_position)

            random.shuffle(neighbors)
            neighbors.sort(key=lambda pos: 0 if pos not in border_set else 1)

            for next_position in neighbors:
                path.append(next_position)
                visited.add(next_position)

                if search():
                    return True

                visited.remove(next_position)
                path.pop()

            return False

        if search():
            return path[:]

        return None

    def create_solved_tiles_from_path(self, path):
        """Creates a solved board from the hidden path, then adds decoys."""
        tiles = []

        for row in range(GRID_SIZE):
            tile_row = []

            for col in range(GRID_SIZE):
                tile_type = random.choice(["straight", "corner"])
                rotation = random.randint(0, 3)
                tile_row.append(PathTile(tile_type, rotation, None))

            tiles.append(tile_row)

        for index, position in enumerate(path):
            row, col = position

            if index == 0:
                next_position = path[index + 1]
                exit_direction = self.get_direction_between(position, next_position)
                tiles[row][col] = self.create_terminal_tile("source", exit_direction)

            elif index == len(path) - 1:
                previous_position = path[index - 1]
                entry_direction = self.get_direction_between(position, previous_position)
                tiles[row][col] = self.create_terminal_tile("goal", entry_direction)

            else:
                previous_position = path[index - 1]
                next_position = path[index + 1]

                entry_direction = self.get_direction_between(position, previous_position)
                exit_direction = self.get_direction_between(position, next_position)

                tiles[row][col] = self.create_path_tile_from_connections(
                    {entry_direction, exit_direction}
                )

        return tiles

    def create_terminal_tile(self, tile_type, direction):
        """Creates a fixed source or goal tile pointing in the needed direction."""
        if tile_type == "source":
            rotation = (direction - RIGHT) % 4
        else:
            rotation = (direction - LEFT) % 4

        return PathTile(tile_type, rotation, rotation)

    def create_path_tile_from_connections(self, connections):
        """Creates a straight or corner tile that matches two openings."""
        connections = set(connections)

        if connections == {UP, DOWN}:
            return PathTile("straight", 0, 0)

        if connections == {LEFT, RIGHT}:
            return PathTile("straight", 1, 1)

        corner_rotations = {
            frozenset({UP, RIGHT}): 0,
            frozenset({RIGHT, DOWN}): 1,
            frozenset({DOWN, LEFT}): 2,
            frozenset({LEFT, UP}): 3,
        }

        rotation = corner_rotations[frozenset(connections)]
        return PathTile("corner", rotation, rotation)

    def scramble_tiles_for_difficulty(self, tiles, path):
        """Scrambles the board and returns the hidden-path rotation cost."""
        internal_path_positions = path[1:-1]
        rotation_needs = self.create_rotation_needs(len(internal_path_positions))

        for index, position in enumerate(internal_path_positions):
            row, col = position
            tile = tiles[row][col]
            rotations_needed = rotation_needs[index]
            tile.rotation = (tile.solution_rotation - rotations_needed) % 4

        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                if (row, col) in path:
                    continue

                tiles[row][col].rotation = random.randint(0, 3)

        return sum(rotation_needs)

    def create_rotation_needs(self, tile_count):
        """Creates per-tile rotation needs inside the difficulty target range."""
        min_cost, max_cost = self.settings["rotation_cost_range"]

        for _ in range(300):
            needs = [random.randint(1, 3) for _ in range(tile_count)]
            total = sum(needs)

            if min_cost <= total <= max_cost:
                return needs

        needs = [1 for _ in range(tile_count)]
        index = 0

        while sum(needs) < min_cost and needs:
            if needs[index] < 3:
                needs[index] += 1

            index = (index + 1) % len(needs)

        return needs

    def reset(self):
        """Creates a fully new path and scramble."""
        self.generate_new_board()

    def rotate_tile(self, row, col):
        """Rotates one selected tile."""
        return self.tiles[row][col].rotate()

    # ------------------------------------------------------------------
    # Path checking
    # ------------------------------------------------------------------

    def in_bounds(self, row, col):
        """Returns True if the position is inside the board."""
        return 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE

    def get_direction_between(self, from_position, to_position):
        """Returns the direction from one adjacent cell to another."""
        from_row, from_col = from_position
        to_row, to_col = to_position
        row_difference = to_row - from_row
        col_difference = to_col - from_col

        for direction, vector in DIRECTION_VECTORS.items():
            if vector == (row_difference, col_difference):
                return direction

        raise ValueError("Positions are not adjacent in the solution path.")

    def tiles_connect(self, row, col, direction):
        """Returns True if this tile connects to its neighbor in one direction."""
        return self.tiles_connect_on_board(self.tiles, row, col, direction)

    def tiles_connect_on_board(self, tiles, row, col, direction):
        """Checks connection between two neighboring tiles."""
        current_tile = tiles[row][col]

        if direction not in current_tile.get_connections():
            return False

        row_change, col_change = DIRECTION_VECTORS[direction]
        next_row = row + row_change
        next_col = col + col_change

        if not self.in_bounds(next_row, next_col):
            return False

        neighbor_tile = tiles[next_row][next_col]
        opposite = OPPOSITE_DIRECTION[direction]

        return opposite in neighbor_tile.get_connections()

    def get_connected_tiles(self):
        """Returns all tiles currently connected to the source tile."""
        return self.get_connected_tiles_on_board(self.tiles, self.start)

    def get_connected_tiles_on_board(self, tiles, start):
        """BFS flood-fill from the source through matching openings."""
        queue = deque([start])
        visited = {start}

        while queue:
            row, col = queue.popleft()

            for direction in (UP, RIGHT, DOWN, LEFT):
                if not self.tiles_connect_on_board(tiles, row, col, direction):
                    continue

                row_change, col_change = DIRECTION_VECTORS[direction]
                next_position = (row + row_change, col + col_change)

                if next_position not in visited:
                    visited.add(next_position)
                    queue.append(next_position)

        return visited

    def get_connected_count_on_board(self, tiles, start):
        """Counts how many cells are linked to the source on a candidate board."""
        return len(self.get_connected_tiles_on_board(tiles, start))

    def has_valid_path(self):
        """Returns True when the source connects to the goal."""
        return self.goal in self.get_connected_tiles()

    def has_valid_path_on_board(self, tiles, start, goal):
        """Returns True if a candidate board connects source to goal."""
        return goal in self.get_connected_tiles_on_board(tiles, start)

    def get_remaining_solution_cost(self):
        """Returns how many clockwise rotations remain on the hidden path."""
        return self.get_remaining_solution_cost_on_board(self.tiles)

    def get_remaining_solution_cost_on_board(self, tiles):
        """Returns hidden-path rotation cost for a simulated board."""
        total_cost = 0

        for row, col in self.solution_path[1:-1]:
            tile = tiles[row][col]

            if tile.solution_rotation is None:
                continue

            total_cost += (tile.solution_rotation - tile.rotation) % 4

        return total_cost

    def get_solution_frontier_score(self):
        """Returns true ordered progress along the hidden source-to-goal path."""
        return self.get_solution_frontier_score_on_board(self.tiles)

    def get_solution_frontier_score_on_board(self, tiles):
        """Returns how far the source-linked route advances along the solution path."""
        if not self.solution_path:
            return 0

        score = 1

        for index in range(len(self.solution_path) - 1):
            row, col = self.solution_path[index]
            next_position = self.solution_path[index + 1]
            direction = self.get_direction_between((row, col), next_position)

            if self.tiles_connect_on_board(tiles, row, col, direction):
                score += 1
            else:
                break

        return score

    # ------------------------------------------------------------------
    # AI scoring helpers
    # ------------------------------------------------------------------

    def get_rotatable_positions(self):
        """Returns all non-terminal tiles the AI or player can rotate."""
        positions = []

        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                if self.tiles[row][col].tile_type in ROTATABLE_TILE_TYPES:
                    positions.append((row, col))

        return positions

    def copy_tiles(self, tiles=None):
        """Creates a copy of the tile grid for one-move simulations."""
        source_tiles = self.tiles if tiles is None else tiles
        copied_tiles = []

        for row in range(GRID_SIZE):
            copied_row = []

            for col in range(GRID_SIZE):
                copied_row.append(source_tiles[row][col].copy())

            copied_tiles.append(copied_row)

        return copied_tiles

    def get_path_order_bonus(self, row, col, frontier_score):
        """Rewards AI moves near the current solution frontier."""
        position = (row, col)

        if position not in self.solution_positions:
            return -12

        path_index = self.solution_path.index(position)
        distance_from_frontier = abs(path_index - frontier_score)

        return max(0, 28 - distance_from_frontier * 5)

    def choose_ai_move(self, random_noise=0.25):
        """Chooses one smart Fox AI move using simulation-based scoring."""
        if self.has_valid_path():
            return None

        rotatable_positions = self.get_rotatable_positions()

        if not rotatable_positions:
            return None

        before_frontier = self.get_solution_frontier_score()
        before_cost = self.get_remaining_solution_cost()
        before_connected_count = len(self.get_connected_tiles())

        best_score = -999999
        best_moves = []

        for row, col in rotatable_positions:
            simulated_tiles = self.copy_tiles()
            simulated_tiles[row][col].rotate()

            score = self.score_ai_move(
                row,
                col,
                simulated_tiles,
                before_frontier,
                before_cost,
                before_connected_count,
                random_noise,
            )

            if score > best_score:
                best_score = score
                best_moves = [(row, col)]
            elif score == best_score:
                best_moves.append((row, col))

        return random.choice(best_moves)

    def score_ai_move(
        self,
        row,
        col,
        simulated_tiles,
        before_frontier,
        before_cost,
        before_connected_count,
        random_noise,
    ):
        """
        Scores a simulated one-rotation move.

        This version makes the Fox more competitive by prioritizing the current
        frontier tile, finishing moves, and direct solution progress.
        """
        if self.has_valid_path_on_board(simulated_tiles, self.start, self.goal):
            return 50000

        after_frontier = self.get_solution_frontier_score_on_board(simulated_tiles)
        after_cost = self.get_remaining_solution_cost_on_board(simulated_tiles)
        after_connected_count = self.get_connected_count_on_board(simulated_tiles, self.start)

        frontier_gain = after_frontier - before_frontier
        cost_improvement = before_cost - after_cost
        connected_gain = after_connected_count - before_connected_count

        score = 0

        # Ordered path progress matters most.
        score += frontier_gain * 230

        # Reducing the remaining solution rotations is the second priority.
        score += cost_improvement * 95

        # Connected region growth is useful, but less important than real path progress.
        score += connected_gain * 10

        position = (row, col)

        # Prefer real solution tiles heavily.
        if position in self.solution_positions:
            score += 55
        else:
            score -= 70

        # Strongly target the exact tile blocking the current path.
        if before_frontier < len(self.solution_path):
            next_frontier_tile = self.solution_path[before_frontier]

            if position == next_frontier_tile:
                score += 230
            else:
                score += self.get_path_order_bonus(row, col, before_frontier)

        # Punish anything that moves the Fox away from the real solution.
        if cost_improvement < 0:
            score -= 145

        if frontier_gain < 0:
            score -= 180

        # Tiny randomness prevents identical behavior without making it look foolish.
        score += random.uniform(-random_noise, random_noise)
        return score

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface, cursor, label_font, tiny_font):
        """Draws the full board."""
        connected_tiles = self.get_connected_tiles()
        board_rect = pygame.Rect(
            self.grid_x - 14,
            self.grid_y - 14,
            BOARD_PIXEL_SIZE + 28,
            BOARD_PIXEL_SIZE + 28,
        )

        draw_soft_glow(surface, board_rect.center, 190, self.accent_color, 45)

        panel = pygame.Surface((board_rect.width, board_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(panel, (2, 7, 10, 205), panel.get_rect(), border_radius=22)
        pygame.draw.rect(panel, (*self.accent_color, 155), panel.get_rect(), 2, border_radius=22)
        pygame.draw.rect(panel, (248, 220, 145, 42), panel.get_rect().inflate(-10, -10), 1, border_radius=17)
        pygame.draw.rect(panel, (0, 0, 0, 75), panel.get_rect().inflate(-24, -24), 2, border_radius=14)
        surface.blit(panel, board_rect.topleft)

        self.draw_board_twinkles(surface, board_rect)

        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                is_connected = (row, col) in connected_tiles
                self.draw_tile(surface, row, col, is_connected, label_font)

        self.draw_cursor(surface, cursor)

    def draw_board_twinkles(self, surface, board_rect):
        """Adds small rune-like twinkles around the board edges."""
        ticks = pygame.time.get_ticks()

        for index in range(18):
            t = (ticks * 0.002 + index * 1.7)
            alpha = int(30 + 70 * (0.5 + 0.5 * math.sin(t)))

            if index % 4 == 0:
                x = board_rect.left + 18 + (index * 37) % (board_rect.width - 36)
                y = board_rect.top + 12
            elif index % 4 == 1:
                x = board_rect.right - 12
                y = board_rect.top + 18 + (index * 31) % (board_rect.height - 36)
            elif index % 4 == 2:
                x = board_rect.left + 18 + (index * 41) % (board_rect.width - 36)
                y = board_rect.bottom - 12
            else:
                x = board_rect.left + 12
                y = board_rect.top + 18 + (index * 29) % (board_rect.height - 36)

            pygame.draw.circle(surface, (*self.accent_color, alpha), (x, y), 2)
            pygame.draw.circle(surface, (*WHITE, alpha // 2), (x, y), 1)

    def draw_tile(self, surface, row, col, is_connected, label_font):
        """Draws one code-rendered stone path tile."""
        rect = get_cell_rect(self.grid_x, self.grid_y, row, col)
        center = rect.center
        tile = self.tiles[row][col]

        pygame.draw.rect(surface, STONE_FILL_DARK, rect)

        inner_rect = rect.inflate(-5, -5)
        pygame.draw.rect(surface, STONE_FILL, inner_rect, border_radius=10)
        pygame.draw.rect(surface, STONE_EDGE, inner_rect, 1, border_radius=10)

        detail_color = (47, 61, 57)
        pygame.draw.line(surface, detail_color, (rect.left + 16, rect.top + 21), (rect.left + 34, rect.top + 14), 1)
        pygame.draw.line(surface, detail_color, (rect.right - 18, rect.bottom - 26), (rect.right - 36, rect.bottom - 15), 1)
        pygame.draw.circle(surface, (50, 62, 55), (rect.left + 18, rect.top + 18), 5, 1)
        pygame.draw.circle(surface, (61, 66, 56), (rect.right - 18, rect.bottom - 18), 4, 1)

        rune_alpha = 42 if not is_connected else 92
        pygame.draw.circle(surface, (*self.accent_color, rune_alpha), center, 24, 1)
        pygame.draw.circle(surface, (*self.accent_color, rune_alpha // 2), center, 34, 1)

        connections = tile.get_connections()
        path_color = self.accent_color if is_connected else self.dim_color
        path_width = 17 if is_connected else 12

        if is_connected:
            draw_soft_glow(surface, center, 40, self.accent_color, 38)

        for direction in connections:
            endpoint = self.get_path_endpoint(rect, direction)
            pygame.draw.line(surface, (2, 6, 8), center, endpoint, path_width + 9)

        for direction in connections:
            endpoint = self.get_path_endpoint(rect, direction)
            pygame.draw.line(surface, path_color, center, endpoint, path_width)

            if is_connected:
                pygame.draw.line(surface, WHITE, center, endpoint, 3)

        pygame.draw.circle(surface, (2, 6, 8), center, path_width // 2 + 10)
        pygame.draw.circle(surface, path_color, center, path_width // 2 + 5)

        if is_connected:
            pygame.draw.circle(surface, WHITE, center, 4)
            pygame.draw.rect(surface, (*self.accent_color, 190), inner_rect, 2, border_radius=10)

        if tile.tile_type == "source":
            self.draw_terminal(surface, rect, "S", label_font, self.accent_color)
        elif tile.tile_type == "goal":
            self.draw_terminal(surface, rect, "F", label_font, SOFT_GOLD)

    def draw_terminal(self, surface, rect, label, font, color):
        """Draws a source/goal marker without changing path orientation."""
        center = rect.center
        draw_soft_glow(surface, center, 44, color, 75)
        pygame.draw.circle(surface, (2, 6, 8), center, 25)
        pygame.draw.circle(surface, color, center, 23, 3)
        pygame.draw.circle(surface, WHITE, center, 13, 1)

        text_surf = font.render(label, True, color).convert_alpha()
        text_rect = text_surf.get_rect(center=center)
        surface.blit(text_surf, text_rect)

    def draw_cursor(self, surface, cursor):
        """Draws a clear animated selector around the current tile."""
        row, col = cursor
        rect = get_cell_rect(self.grid_x, self.grid_y, row, col)
        pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.007)
        expanded = rect.inflate(12, 12)

        draw_soft_glow(surface, rect.center, int(58 + pulse * 12), self.accent_color, int(90 + pulse * 50))
        pygame.draw.rect(surface, self.accent_color, expanded, 4, border_radius=14)
        pygame.draw.rect(surface, WHITE, expanded.inflate(-6, -6), 1, border_radius=10)

    def get_path_endpoint(self, rect, direction):
        """Returns the edge point a path arm should reach."""
        center_x, center_y = rect.center

        if direction == UP:
            return (center_x, rect.top)
        if direction == RIGHT:
            return (rect.right, center_y)
        if direction == DOWN:
            return (center_x, rect.bottom)
        if direction == LEFT:
            return (rect.left, center_y)

        return rect.center


class StarlightCrossingGridGame:
    """
    Playable puzzle state for Starlight Crossing.

    Modes:
    - Single-player: the Fox board is solved by a paced heuristic AI.
    - Local multiplayer: the Fox board is controlled with arrows + ENTER.

    The selected mode is passed in by game.py or the standalone demo launcher.
    This class manages puzzle generation, input, scoring, reward selection, and
    completion state.
    """

    def __init__(
        self,
        game_mode=MODE_SINGLE_PLAYER,
        difficulty=DEFAULT_DIFFICULTY,
        standalone_debug=True,
        round_seconds=ROUND_TIME_SECONDS,
    ):
        raw_bg = load_image(GAME_BACKGROUND_PATH)
        self.background = (
            pygame.transform.smoothscale(raw_bg, (SCREEN_WIDTH, SCREEN_HEIGHT))
            if raw_bg else None
        )

        self.font_title = load_font(FANTASY_FONT_PATH, 32, bold=True)
        self.font_small = load_font(FANTASY_FONT_PATH, 16)
        self.font_tiny = load_font(FANTASY_FONT_PATH, 14)
        self.font_label = load_font(FANTASY_FONT_PATH, 22, bold=True)
        self.font_banner = load_font(FANTASY_FONT_PATH, 30, bold=True)
        self.font_timer = load_font(FANTASY_FONT_PATH, 40, bold=True)

        raw_hourglass_full = load_image(HOURGLASS_FULL_PATH)
        raw_hourglass_empty = load_image(HOURGLASS_EMPTY_PATH)

        self.hourglass_full_image = self.scale_image_to_height(raw_hourglass_full, 44)
        self.hourglass_empty_image = self.scale_image_to_height(raw_hourglass_empty, 44)

        self.reward_select_images = {
            WINNER_EXPLORER: self.load_fullscreen_image(STARLIGHT_REWARD_EXPLORER_SELECT_PATH),
            WINNER_FOX: self.load_fullscreen_image(STARLIGHT_REWARD_FOX_SELECT_PATH),
        }

        self.reward_chosen_images = {
            REWARD_GROVE_CALM: self.load_fullscreen_image(STARLIGHT_REWARD_GROVE_CALM_PATH),
            REWARD_LANTERN_SHIELD: self.load_fullscreen_image(STARLIGHT_REWARD_LANTERN_SHIELD_PATH),
            REWARD_FOX_BANISH: self.load_fullscreen_image(STARLIGHT_REWARD_FOX_BANISH_PATH),
            REWARD_MISCHIEF_SURGE: self.load_fullscreen_image(STARLIGHT_REWARD_MISCHIEF_SURGE_PATH),
            REWARD_SHADOW_RUSH: self.load_fullscreen_image(STARLIGHT_REWARD_SHADOW_RUSH_PATH),
            REWARD_PORTAL_FLICKER: self.load_fullscreen_image(STARLIGHT_REWARD_PORTAL_FLICKER_PATH),
        }

        self.complete_screen_image = self.load_fullscreen_image(STARLIGHT_CROSSING_COMPLETE_PATH)

        self.game_mode = game_mode
        self.difficulty = difficulty
        self.difficulty_settings = DIFFICULTY_SETTINGS[difficulty]
        self.standalone_debug = standalone_debug  # Retained for launcher compatibility.
        self.round_frames_total = round_seconds * FPS

        self.twinkles = self.create_twinkles()
        self.reward_phase = REWARD_PHASE_NONE
        self.reward_timer = 0
        self.reward_transition_timer = 0

        # Main maze context passed in from game.py.
        self.portal_active = False
        self.grove_shift_meter = 0
        self.shards_collected = 0
        self.fox_urgency = 0

        self.selected_reward = None
        self.final_winner = None
        self.reward_options = []
        self.mini_game_finished = False

        self.create_new_duel()

    def load_fullscreen_image(self, path):
        """Loads a full-screen UI image and scales it to the game window."""
        image = load_image(path)

        if image is None:
            return None

        return pygame.transform.smoothscale(image, (SCREEN_WIDTH, SCREEN_HEIGHT))

    def create_twinkles(self):
        """Creates persistent background twinkle positions for the gameplay screen."""
        twinkles = []

        for _ in range(125):
            side_bias = random.choice(["left", "right", "center", "any"])

            if side_bias == "left":
                x = random.randint(0, 440)
                color = random.choice([TEAL_1, TEAL_2, WHITE])
            elif side_bias == "right":
                x = random.randint(584, SCREEN_WIDTH)
                color = random.choice([PURPLE_1, PURPLE_2, WHITE])
            else:
                x = random.randint(0, SCREEN_WIDTH)
                color = random.choice([TEAL_1, PURPLE_1, WHITE, SOFT_GOLD])

            y = random.randint(120, SCREEN_HEIGHT - 35)
            twinkles.append({
                "x": x,
                "y": y,
                "size": random.choice([1, 1, 1, 2]),
                "phase": random.uniform(0, math.tau),
                "speed": random.uniform(0.0015, 0.0045),
                "color": color,
            })

        return twinkles
    
    def scale_image_to_height(self, image, target_height):
        """Scales an image by height while preserving its original proportions."""
        if image is None:
            return None

        original_width = image.get_width()
        original_height = image.get_height()

        if original_height == 0:
            return image

        scale_ratio = target_height / original_height
        new_width = int(original_width * scale_ratio)

        return pygame.transform.smoothscale(image, (new_width, target_height))

    def draw_timer_display(self, surface, alpha):
        """
        Draws the timer with a simple animated hourglass.

        This uses the same stable style as Sigil's Echo:
        the image alternates between full and empty instead of rotating.
        """
        seconds_left = self.get_time_remaining_seconds()
        timer_color = SOFT_GOLD if seconds_left <= 10 and self.winner is None else WHITE

        timer_text = f"TIME {self.format_time_remaining()}"

        # Alternate hourglass image every 350 ms.
        flip_frame = (pygame.time.get_ticks() // 350) % 2

        if flip_frame == 0:
            hourglass = self.hourglass_full_image
        else:
            hourglass = self.hourglass_empty_image

        timer_center = (SCREEN_WIDTH // 2, 180)
        icon_x = timer_center[0] - 92
        text_x = timer_center[0] + 26

        if hourglass:
            icon = hourglass.copy()
            icon.set_alpha(alpha)
            icon_rect = icon.get_rect(center=(icon_x, timer_center[1] + 2))
            surface.blit(icon, icon_rect)
        else:
            draw_text_center(
                surface,
                "⌛",
                self.font_timer,
                timer_color,
                (icon_x, timer_center[1]),
                alpha=alpha,
            )

        draw_text_center(
            surface,
            timer_text,
            self.font_timer,
            timer_color,
            (text_x, timer_center[1]),
            alpha=alpha,
        )

    def create_new_duel(self):
        """Creates fresh playable boards for both sides."""
        self.explorer_board = SolvingBoard(
            EXPLORER_GRID_X,
            GRID_Y,
            TEAL_1,
            DIM_TEAL_PATH,
            "EXPLORER",
            difficulty=self.difficulty,
        )

        self.fox_board = SolvingBoard(
            FOX_GRID_X,
            GRID_Y,
            PURPLE_1,
            DIM_PURPLE_PATH,
            "FOX",
            difficulty=self.difficulty,
        )

        self.explorer_cursor = list(self.explorer_board.start)
        self.fox_cursor = list(self.fox_board.start)

        self.explorer_moves = 0
        self.fox_moves = 0

        self.fox_ai_decision_timer = 0
        self.fox_ai_cursor_step_timer = 0
        self.fox_ai_rotate_timer = 0
        self.fox_ai_target = None
        self.last_fox_ai_move = None

        self.round_frames_remaining = self.round_frames_total
        self.round_ended_by_time = False
        self.winner = None

        self.reward_phase = REWARD_PHASE_NONE
        self.reward_timer = 0
        self.reward_transition_timer = 0
        self.selected_reward = None
        self.final_winner = None
        self.reward_options = []
        self.mini_game_finished = False

    # ------------------------------------------------------------------
    # Mode, input, and update
    # ------------------------------------------------------------------

    def clear_fox_ai_action(self):
        """Clears any in-progress Fox AI cursor motion."""
        self.fox_ai_decision_timer = 0
        self.fox_ai_cursor_step_timer = 0
        self.fox_ai_rotate_timer = 0
        self.fox_ai_target = None

    def handle_keydown(self, key):
        """Handles real gameplay keyboard input."""
        if self.reward_phase == REWARD_PHASE_SELECT:
            self.handle_reward_key(key)
            return

        if self.reward_phase in (
            REWARD_PHASE_WIN_SEQUENCE,
            REWARD_PHASE_TO_CLAIMED,
            REWARD_PHASE_CLAIMED,
            REWARD_PHASE_COMPLETE,
        ):
            return

        if self.winner is not None:
            return

        # Explorer controls.
        if key == pygame.K_w:
            self.move_cursor(self.explorer_cursor, -1, 0)
        elif key == pygame.K_s:
            self.move_cursor(self.explorer_cursor, 1, 0)
        elif key == pygame.K_a:
            self.move_cursor(self.explorer_cursor, 0, -1)
        elif key == pygame.K_d:
            self.move_cursor(self.explorer_cursor, 0, 1)
        elif key == pygame.K_SPACE:
            self.rotate_explorer_tile()

        # Fox controls only apply in local multiplayer.
        if self.game_mode != MODE_LOCAL_MULTIPLAYER:
            return

        if key == pygame.K_UP:
            self.move_cursor(self.fox_cursor, -1, 0)
        elif key == pygame.K_DOWN:
            self.move_cursor(self.fox_cursor, 1, 0)
        elif key == pygame.K_LEFT:
            self.move_cursor(self.fox_cursor, 0, -1)
        elif key == pygame.K_RIGHT:
            self.move_cursor(self.fox_cursor, 0, 1)
        elif key == pygame.K_RETURN:
            self.rotate_fox_tile()

    def update(self):
        """Updates timer, single-player Fox AI, and reward flow."""
        if self.reward_phase != REWARD_PHASE_NONE:
            self.update_reward_flow()
            return

        if self.winner is not None:
            return

        self.round_frames_remaining = max(0, self.round_frames_remaining - 1)

        if self.round_frames_remaining <= 0:
            self.resolve_timed_round()
            return

        if self.game_mode == MODE_SINGLE_PLAYER:
            self.update_fox_ai()


    def get_adaptive_fox_ai_interval(self):
        """
        Returns the Fox AI decision interval for the current moment.

        The Fox becomes more aggressive when the Explorer is ahead or when
        the timer is running low, making it feel like a real opponent.
        """
        base_interval = self.difficulty_settings["fox_ai_move_interval"]

        if self.round_frames_total <= 0:
            return base_interval

        time_ratio = self.round_frames_remaining / self.round_frames_total

        explorer_progress = self.explorer_board.get_solution_frontier_score()
        fox_progress = self.fox_board.get_solution_frontier_score()

        explorer_path_length = max(len(self.explorer_board.solution_path), 1)
        fox_path_length = max(len(self.fox_board.solution_path), 1)

        explorer_progress_ratio = explorer_progress / explorer_path_length
        fox_progress_ratio = fox_progress / fox_path_length

        pressure_bonus = 0
        fox_urgency = max(0, min(100, getattr(self, "fox_urgency", 0)))

        # Main-game urgency makes the Starlight fox solve faster.
        if fox_urgency >= 80:
            pressure_bonus += 18
        elif fox_urgency >= 60:
            pressure_bonus += 12
        elif fox_urgency >= 40:
            pressure_bonus += 7

        # If the Explorer is ahead, the Fox starts pushing harder.
        if explorer_progress_ratio > fox_progress_ratio:
            pressure_bonus += 14

        # If the Explorer is close to finishing, the Fox becomes urgent.
        if explorer_progress_ratio >= 0.65:
            pressure_bonus += 10

        if explorer_progress_ratio >= 0.80:
            pressure_bonus += 12

        # Final stretch pressure.
        if time_ratio <= 0.45:
            pressure_bonus += 8

        if time_ratio <= 0.25:
            pressure_bonus += 10

        # If the player is making lots of moves, the Fox reacts faster.
        if self.explorer_moves >= self.fox_moves + 4:
            pressure_bonus += 6

        return max(FOX_AI_MIN_MOVE_INTERVAL, base_interval - pressure_bonus)

    def update_fox_ai(self):
        """Updates the paced Fox AI solver with adaptive pressure."""
        if self.fox_ai_target is not None:
            self.update_fox_ai_motion()
            return

        self.fox_ai_decision_timer += 1

        current_interval = self.get_adaptive_fox_ai_interval()

        if self.fox_ai_decision_timer < current_interval:
            return

        self.fox_ai_decision_timer = 0

        fox_urgency = max(0, min(100, getattr(self, "fox_urgency", 0)))
        urgency_ratio = fox_urgency / 100

        skip_chance = self.difficulty_settings["fox_ai_think_skip_chance"]
        skip_chance = max(0.0, skip_chance - urgency_ratio * 0.08)

        if random.random() < skip_chance:
            return

        random_noise = self.difficulty_settings["fox_ai_random_noise"]
        random_noise = max(0.01, random_noise * (1.0 - urgency_ratio * 0.65))

        move = self.fox_board.choose_ai_move(
            random_noise=random_noise
        )

        if move is not None:
            self.fox_ai_target = move
            self.fox_ai_cursor_step_timer = 0
            self.fox_ai_rotate_timer = 0

    def update_fox_ai_motion(self):
        """Moves the Fox cursor toward its chosen tile before rotating it."""
        target_row, target_col = self.fox_ai_target
        current_row, current_col = self.fox_cursor

        if (current_row, current_col) != (target_row, target_col):
            self.fox_ai_cursor_step_timer += 1

            if self.fox_ai_cursor_step_timer < FOX_AI_CURSOR_STEP_INTERVAL:
                return

            self.fox_ai_cursor_step_timer = 0

            if current_row < target_row:
                self.fox_cursor[0] += 1
            elif current_row > target_row:
                self.fox_cursor[0] -= 1
            elif current_col < target_col:
                self.fox_cursor[1] += 1
            elif current_col > target_col:
                self.fox_cursor[1] -= 1

            return

        self.fox_ai_rotate_timer += 1

        if self.fox_ai_rotate_timer < FOX_AI_ROTATE_DELAY:
            return

        self.make_fox_ai_move_at_target()

    def make_fox_ai_move_at_target(self):
        """Rotates the target tile once after the Fox cursor reaches it."""
        if self.fox_ai_target is None:
            return

        row, col = self.fox_ai_target

        if self.fox_board.rotate_tile(row, col):
            self.fox_moves += 1
            self.last_fox_ai_move = (row, col)

        self.clear_fox_ai_action()
        self.check_for_winner()

    def move_cursor(self, cursor, row_change, col_change):
        """Moves a board cursor while staying inside the grid."""
        cursor[0] = max(0, min(GRID_SIZE - 1, cursor[0] + row_change))
        cursor[1] = max(0, min(GRID_SIZE - 1, cursor[1] + col_change))

    def rotate_explorer_tile(self):
        """Rotates the explorer-selected tile."""
        row, col = self.explorer_cursor

        if self.explorer_board.rotate_tile(row, col):
            self.explorer_moves += 1
            self.check_for_winner()

    def rotate_fox_tile(self):
        """Rotates the fox-selected tile for local multiplayer."""
        row, col = self.fox_cursor

        if self.fox_board.rotate_tile(row, col):
            self.fox_moves += 1
            self.check_for_winner()

    def check_for_winner(self):
        """Checks whether either board completed its crossing."""
        if self.winner is not None:
            return

        explorer_complete = self.explorer_board.has_valid_path()
        fox_complete = self.fox_board.has_valid_path()

        if explorer_complete and fox_complete:
            self.winner = "tie"
        elif explorer_complete:
            self.winner = "explorer"
        elif fox_complete:
            self.winner = "fox"

        if self.winner is not None:
            self.start_reward_flow()

    # ------------------------------------------------------------------
    # Timer and scoring
    # ------------------------------------------------------------------

    def get_time_remaining_seconds(self):
        """Returns the number of whole seconds left in the round."""
        return max(0, math.ceil(self.round_frames_remaining / FPS))

    def format_time_remaining(self):
        """Formats the timer as M:SS."""
        seconds = self.get_time_remaining_seconds()
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"

    def get_closeness_score(self, board):
        """
        Scores how close a board is to winning.

        Priority:
        1. Ordered frontier progress along the real hidden solution path.
        2. Number of source-connected solution tiles.
        3. Lower remaining rotation cost.
        4. Fewer moves as a final tie-breaker.
        """
        frontier_score = board.get_solution_frontier_score()
        connected_tiles = board.get_connected_tiles()
        connected_solution_tiles = len(connected_tiles.intersection(board.solution_positions))
        remaining_cost = board.get_remaining_solution_cost()
        moves = self.explorer_moves if board is self.explorer_board else self.fox_moves

        return (
            frontier_score,
            connected_solution_tiles,
            -remaining_cost,
            -moves,
        )

    def resolve_timed_round(self):
        """Ends the round and awards the win to the closest real solution progress."""
        self.round_ended_by_time = True

        explorer_score = self.get_closeness_score(self.explorer_board)
        fox_score = self.get_closeness_score(self.fox_board)

        if explorer_score > fox_score:
            self.winner = "explorer_time"
        elif fox_score > explorer_score:
            self.winner = "fox_time"
        else:
            self.winner = "tie_time"

        self.start_reward_flow()

    # ------------------------------------------------------------------
    # Reward flow
    # ------------------------------------------------------------------

    def start_reward_flow(self):
        """
        Starts the reward sequence after the Starlight Crossing winner is known.

        This does not apply the reward to the maze yet. It only lets the winning
        side choose a reward and stores the chosen reward for game.py later.
        """
        if self.winner in ("explorer", "explorer_time"):
            self.final_winner = WINNER_EXPLORER
            self.reward_options = EXPLORER_REWARDS

        elif self.winner in ("fox", "fox_time"):
            self.final_winner = WINNER_FOX
            self.reward_options = FOX_REWARDS

        else:
            self.final_winner = WINNER_TIE
            self.reward_options = []

        self.selected_reward = None
        self.reward_phase = REWARD_PHASE_WIN_SEQUENCE
        self.reward_timer = 0
        self.reward_transition_timer = 0


    def update_reward_flow(self):
        """Updates winner reveal, reward selection, reward chosen, and complete screens."""
        if self.reward_phase == REWARD_PHASE_NONE:
            return

        if self.reward_phase == REWARD_PHASE_WIN_SEQUENCE:
            self.reward_timer += 1

            if self.reward_timer >= WIN_SEQUENCE_FRAMES:
                if self.final_winner == WINNER_TIE:
                    self.reward_phase = REWARD_PHASE_COMPLETE
                else:
                    self.reward_phase = REWARD_PHASE_SELECT

                self.reward_timer = 0
                self.reward_transition_timer = 0

        elif self.reward_phase == REWARD_PHASE_SELECT:
            if self.game_mode == MODE_SINGLE_PLAYER and self.final_winner == WINNER_FOX:
                self.reward_timer += 1

                if self.reward_timer >= AI_REWARD_PREVIEW_FRAMES:
                    self.selected_reward = self.choose_ai_fox_reward()
                    self.reward_phase = REWARD_PHASE_TO_CLAIMED
                    self.reward_transition_timer = 0
                    self.reward_timer = 0

        elif self.reward_phase == REWARD_PHASE_TO_CLAIMED:
            self.reward_transition_timer += 1

            if self.reward_transition_timer >= REWARD_TRANSITION_FRAMES:
                self.reward_phase = REWARD_PHASE_CLAIMED
                self.reward_timer = 0

        elif self.reward_phase == REWARD_PHASE_CLAIMED:
            self.reward_timer += 1

            if self.reward_timer >= REWARD_CLAIMED_HOLD_FRAMES:
                self.reward_phase = REWARD_PHASE_COMPLETE
                self.reward_timer = 0

        elif self.reward_phase == REWARD_PHASE_COMPLETE:
            self.reward_timer += 1

            if self.reward_timer >= COMPLETE_HOLD_FRAMES:
                self.mini_game_finished = True


    def choose_ai_fox_reward(self):
        """Chooses a Fox reward automatically using main-game strategy."""
        explorer_progress = self.explorer_board.get_solution_frontier_score()
        explorer_path_length = max(len(self.explorer_board.solution_path), 1)
        explorer_progress_ratio = explorer_progress / explorer_path_length

        portal_active = getattr(self, "portal_active", False)
        grove_shift = getattr(self, "grove_shift_meter", 0)
        shards_collected = getattr(self, "shards_collected", 0)
        fox_urgency = getattr(self, "fox_urgency", 0)

        # If escape is close, delay the portal.
        if portal_active:
            return REWARD_PORTAL_FLICKER

        if explorer_progress_ratio >= 0.75:
            return REWARD_PORTAL_FLICKER

        if shards_collected >= 2 and fox_urgency >= 55:
            return REWARD_PORTAL_FLICKER

        # If the fox can nearly win through the meter, push the meter.
        if grove_shift >= 70:
            return REWARD_MISCHIEF_SURGE

        if fox_urgency >= 85 and self.round_frames_remaining <= self.round_frames_total * 0.45:
            return REWARD_MISCHIEF_SURGE

        # Default: make the fox more dangerous in the maze.
        return REWARD_SHADOW_RUSH

    def handle_reward_key(self, key):
        """Lets the winning side choose one of three rewards."""
        key_to_index = {
            pygame.K_1: 0,
            pygame.K_2: 1,
            pygame.K_3: 2,
        }

        if key not in key_to_index:
            return

        reward_index = key_to_index[key]

        if reward_index >= len(self.reward_options):
            return

        self.selected_reward = self.reward_options[reward_index]["id"]
        self.reward_phase = REWARD_PHASE_TO_CLAIMED
        self.reward_transition_timer = 0
        self.reward_timer = 0


    def get_selected_reward_info(self):
        """Returns the selected reward dictionary, if one has been chosen."""
        if self.selected_reward is None:
            return None

        for reward in EXPLORER_REWARDS + FOX_REWARDS:
            if reward["id"] == self.selected_reward:
                return reward

        return None


    def is_complete(self):
        """
        Returns True only after the final Starlight Crossing Complete screen
        has been shown long enough.
        """
        return self.mini_game_finished


    def get_selected_reward(self):
        """
        Returns the selected reward ID.

        The actual reward effect should be applied later in game.py.
        """
        return self.selected_reward


    def get_final_winner(self):
        """Returns the final winner of Starlight Crossing."""
        return self.final_winner

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw_gameplay_scene(self, surface, alpha):
        """Draws the normal gameplay scene underneath transitions."""
        if self.background:
            surface.blit(self.background, (0, 0))
        else:
            surface.fill((9, 14, 18))

        self.draw_moody_overlay(surface)
        self.draw_twinkles(surface)
        self.draw_side_mists(surface)
        self.draw_headers(surface, alpha)

        self.explorer_board.draw(surface, self.explorer_cursor, self.font_label, self.font_tiny)
        self.fox_board.draw(surface, self.fox_cursor, self.font_label, self.font_tiny)

        self.draw_status(surface, alpha)

        if self.winner is not None:
            self.draw_winner_banner(surface, alpha)
            
    def draw(self, surface, alpha=255):
        """Draws the gameplay screen and smooth reward transitions."""
        alpha = max(0, min(255, alpha))
        game_layer = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

        if self.reward_phase == REWARD_PHASE_WIN_SEQUENCE:
            self.draw_win_sequence_transition(game_layer, alpha)

        elif self.reward_phase == REWARD_PHASE_SELECT:
            self.draw_reward_select(game_layer, alpha)

        elif self.reward_phase == REWARD_PHASE_TO_CLAIMED:
            self.draw_reward_to_claimed_transition(game_layer, alpha)

        elif self.reward_phase == REWARD_PHASE_CLAIMED:
            self.draw_reward_claimed_to_complete_transition(game_layer, alpha)

        elif self.reward_phase == REWARD_PHASE_COMPLETE:
            self.draw_complete_screen(game_layer, alpha)

        else:
            self.draw_gameplay_scene(game_layer, alpha)

        game_layer.set_alpha(alpha)
        surface.blit(game_layer, (0, 0))

    def draw_win_sequence_transition(self, surface, alpha):
        """
        Draws the winner message, then fades smoothly into the next screen.

        Explorer/Fox wins fade into reward selection.
        Ties fade directly into the complete screen.
        """
        self.draw_gameplay_scene(surface, alpha)

        fade_start = max(0, WIN_SEQUENCE_FRAMES - WIN_TO_REWARD_FADE_FRAMES)

        if self.reward_timer < fade_start:
            return

        fade_progress = (self.reward_timer - fade_start) / max(WIN_TO_REWARD_FADE_FRAMES, 1)
        fade_progress = min(max(fade_progress, 0.0), 1.0)
        fade_progress = ease_in_out(fade_progress)

        fade_alpha = int(255 * fade_progress)

        if self.final_winner == WINNER_TIE:
            self.draw_complete_screen(surface, fade_alpha)
        else:
            self.draw_reward_select(surface, fade_alpha)

    def draw_reward_select(self, surface, alpha):
        """Draws the correct full-screen reward selection image."""
        image = self.reward_select_images.get(self.final_winner)

        if image:
            screen_image = image.copy()
            screen_image.set_alpha(alpha)
            surface.blit(screen_image, (0, 0))
        else:
            surface.fill((5, 16, 18))


    def draw_reward_chosen(self, surface, alpha):
        """Draws the full-screen image for the selected reward."""
        image = self.reward_chosen_images.get(self.selected_reward)

        if image:
            screen_image = image.copy()
            screen_image.set_alpha(alpha)
            surface.blit(screen_image, (0, 0))
        else:
            surface.fill((5, 16, 18))


    def draw_complete_screen(self, surface, alpha):
        """Draws the final Starlight Crossing Complete screen."""
        if self.complete_screen_image:
            screen_image = self.complete_screen_image.copy()
            screen_image.set_alpha(alpha)
            surface.blit(screen_image, (0, 0))
        else:
            surface.fill((5, 16, 18))

    def draw_reward_claimed_to_complete_transition(self, surface, alpha):
        """
        Shows the selected reward, then fades into the final complete screen
        near the end of the hold time.
        """
        fade_start = max(0, REWARD_CLAIMED_HOLD_FRAMES - CLAIMED_TO_COMPLETE_FADE_FRAMES)

        if self.reward_timer < fade_start:
            self.draw_reward_chosen(surface, alpha)
            return

        fade_progress = (self.reward_timer - fade_start) / max(CLAIMED_TO_COMPLETE_FADE_FRAMES, 1)
        fade_progress = min(max(fade_progress, 0.0), 1.0)
        fade_progress = ease_in_out(fade_progress)

        chosen_alpha = int(255 * (1.0 - fade_progress))
        complete_alpha = int(255 * fade_progress)

        self.draw_reward_chosen(surface, chosen_alpha)
        self.draw_complete_screen(surface, complete_alpha)


    def draw_reward_to_claimed_transition(self, surface, alpha):
        """Crossfades from reward selection to the selected reward screen."""
        progress = min(self.reward_transition_timer / max(REWARD_TRANSITION_FRAMES, 1), 1.0)
        progress = ease_in_out(progress)

        select_alpha = int(255 * (1.0 - progress))
        chosen_alpha = int(255 * progress)

        self.draw_reward_select(surface, select_alpha)
        self.draw_reward_chosen(surface, chosen_alpha)

    def draw_moody_overlay(self, surface):
        """Adds a subtle moody veil without creating a black border."""
        veil = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 42))
        surface.blit(veil, (0, 0))

        vignette = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        max_radius = 720

        for radius in range(max_radius, 160, -32):
            alpha = int(4 * (1 - radius / max_radius) ** 2)
            pygame.draw.circle(vignette, (0, 0, 0, alpha), center, radius)

        surface.blit(vignette, (0, 0))

    def draw_twinkles(self, surface):
        """Draws animated star particles over the shrine background."""
        ticks = pygame.time.get_ticks()

        for twinkle in self.twinkles:
            brightness = 0.5 + 0.5 * math.sin(ticks * twinkle["speed"] + twinkle["phase"])
            alpha = int(25 + brightness * 125)
            x = twinkle["x"]
            y = twinkle["y"]
            size = twinkle["size"]
            color = twinkle["color"]

            pygame.draw.circle(surface, (*color, alpha), (x, y), size)

            if brightness > 0.82:
                pygame.draw.line(surface, (*color, alpha // 2), (x - 3, y), (x + 3, y), 1)
                pygame.draw.line(surface, (*color, alpha // 2), (x, y - 3), (x, y + 3), 1)

    def draw_side_mists(self, surface):
        """Adds subtle teal and purple haze behind the two boards."""
        draw_soft_glow(surface, (EXPLORER_GRID_X + 120, GRID_Y + 165), 210, TEAL_1, 40)
        draw_soft_glow(surface, (FOX_GRID_X + 250, GRID_Y + 165), 210, PURPLE_1, 42)
        draw_soft_glow(surface, (SCREEN_WIDTH // 2, GRID_Y + 170), 150, SOFT_GOLD, 18)

    def draw_headers(self, surface, alpha):
        """Draws board headers and mode indicator."""
        explorer_center_x = EXPLORER_GRID_X + BOARD_PIXEL_SIZE // 2
        fox_center_x = FOX_GRID_X + BOARD_PIXEL_SIZE // 2
        header_y = GRID_Y - 35

        draw_text_center(surface, "EXPLORER", self.font_title, TEAL_1, (explorer_center_x, header_y), alpha=alpha)
        draw_text_center(surface, "FOX", self.font_title, PURPLE_1, (fox_center_x, header_y), alpha=alpha)

        mode_label = "AI" if self.game_mode == MODE_SINGLE_PLAYER else "LOCAL"
        draw_text_center(
            surface,
            mode_label,
            self.font_tiny,
            MUTED_WHITE,
            (fox_center_x, header_y + 25),
            alpha=int(alpha * 0.88),
        )

    def draw_status(self, surface, alpha):
        """Draws timer and round status text."""
        self.draw_timer_display(surface, alpha)

        if self.winner is not None:
            return

        draw_text_center(
            surface,
            "Complete the crossing before the starlight fades.",
            self.font_small,
            MUTED_WHITE,
            (SCREEN_WIDTH // 2, 670),
            alpha=alpha,
        )

    def draw_winner_banner(self, surface, alpha):
        """Draws result message near the bottom before reward/complete transitions."""
        if self.winner == "explorer":
            text = "THE EXPLORER COMPLETES THE CROSSING!"
            color = TEAL_1

        elif self.winner == "fox":
            text = "THE FOX COMPLETES THE CROSSING!"
            color = PURPLE_1

        elif self.winner == "explorer_time":
            text = "TIME FADES — THE EXPLORER WAS CLOSER!"
            color = TEAL_1

        elif self.winner == "fox_time":
            text = "TIME FADES — THE FOX WAS CLOSER!"
            color = PURPLE_1

        elif self.winner == "tie_time":
            text = "TIME FADES — BOTH PATHS WERE EQUALLY CLOSE!"
            color = SOFT_GOLD

        elif self.winner == "tie":
            text = "BOTH CROSSINGS AWAKEN TOGETHER!"
            color = SOFT_GOLD

        else:
            text = "THE STARLIGHT SETTLES."
            color = SOFT_GOLD

        message_center = (SCREEN_WIDTH // 2, 680)

        draw_soft_glow(surface, message_center, 170, color, 45)

        draw_text_center(
            surface,
            text,
            self.font_banner,
            color,
            message_center,
            alpha=alpha,
            shadow=True,
        )


# ------------------------------------------------------------
# Embedded wrapper and standalone demo
# ------------------------------------------------------------

class StarlightCrossing:
    """
    Embedded wrapper used by game.py.

    This class owns the intro, fade into gameplay, countdown, reward flow, and
    completion state without opening its own Pygame window.
    """

    STATE_INTRO = "intro"
    STATE_FADE_TO_GAME = "fade_to_game"
    STATE_COUNTDOWN = "countdown"
    STATE_GAMEPLAY = "gameplay"

    def __init__(
        self,
        game_mode=MODE_SINGLE_PLAYER,
        difficulty=DEFAULT_DIFFICULTY,
        standalone_debug=False,
    ):
        self.state = self.STATE_INTRO
        self.intro = StarlightCrossingIntro()
        self.gameplay = StarlightCrossingGridGame(
            game_mode=game_mode,
            difficulty=difficulty,
            standalone_debug=standalone_debug,
        )

        self.fade_frame = 0
        self.fade_duration = 70

        self.countdown_timer = 0
        self.countdown_total_frames = FPS * 4

        self.finished = False

    def handle_event(self, event):
        """Handles Starlight Crossing input while embedded in game.py."""
        if event.type != pygame.KEYDOWN:
            return

        if self.state == self.STATE_INTRO:
            if event.key == pygame.K_SPACE and self.intro.frame >= 520:
                self.state = self.STATE_FADE_TO_GAME
                self.fade_frame = 0

        elif self.state == self.STATE_GAMEPLAY:
            self.gameplay.handle_keydown(event.key)

    def update(self):
        """Updates the current Starlight Crossing phase."""
        if self.state == self.STATE_INTRO:
            self.intro.update()

        elif self.state == self.STATE_FADE_TO_GAME:
            self.fade_frame += 1

            if self.fade_frame >= self.fade_duration:
                self.state = self.STATE_COUNTDOWN
                self.countdown_timer = 0

        elif self.state == self.STATE_COUNTDOWN:
            self.countdown_timer += 1

            if self.countdown_timer >= self.countdown_total_frames:
                self.state = self.STATE_GAMEPLAY

        elif self.state == self.STATE_GAMEPLAY:
            self.gameplay.update()

            if self.gameplay.is_complete():
                self.finished = True

    def draw(self, screen):
        """Draws Starlight Crossing onto the main game screen."""
        if self.state == self.STATE_INTRO:
            self.intro.draw(screen)

        elif self.state == self.STATE_FADE_TO_GAME:
            self.intro.draw(screen)

            fade_t = min(self.fade_frame / self.fade_duration, 1.0)
            alpha = int(255 * ease_in_out(fade_t))
            self.gameplay.draw(screen, alpha=alpha)

        elif self.state == self.STATE_COUNTDOWN:
            self.gameplay.draw(screen, alpha=255)
            self.draw_countdown_overlay(screen)

        elif self.state == self.STATE_GAMEPLAY:
            self.gameplay.draw(screen, alpha=255)

    def is_complete(self):
        """Returns True when Starlight Crossing is ready to return to the maze."""
        return self.finished

    def get_selected_reward(self):
        """Returns the selected reward ID for game.py."""
        return self.gameplay.get_selected_reward()

    def get_final_winner(self):
        """Returns the final winner of Starlight Crossing."""
        return self.gameplay.get_final_winner()
    
    def draw_countdown_overlay(self, screen):
        """Draws a short countdown before Starlight Crossing begins."""
        countdown_second = self.countdown_timer // FPS

        if countdown_second == 0:
            message = "3"
        elif countdown_second == 1:
            message = "2"
        elif countdown_second == 2:
            message = "1"
        else:
            message = "GO!"

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 95))
        screen.blit(overlay, (0, 0))

        pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.012)

        draw_soft_glow(
            screen,
            (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2),
            int(120 + pulse * 25),
            SOFT_GOLD,
            90,
        )

        draw_text_center(
            screen,
            message,
            self.gameplay.font_timer,
            SOFT_GOLD,
            (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2),
            alpha=255,
            shadow=True,
        )

        draw_text_center(
            screen,
            "Get ready...",
            self.gameplay.font_small,
            WHITE,
            (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 70),
            alpha=230,
            shadow=True,
        )


class TransitionApp:
    """Standalone demo app for running Starlight Crossing directly."""

    STATE_INTRO = "intro"
    STATE_FADE_TO_GAME = "fade_to_game"
    STATE_COUNTDOWN = "countdown"
    STATE_GAMEPLAY = "gameplay"

    def __init__(
        self,
        game_mode=MODE_SINGLE_PLAYER,
        difficulty=DEFAULT_DIFFICULTY,
        standalone_debug=True,
    ):
        pygame.init()

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Starlight Crossing")

        self.clock = pygame.time.Clock()
        self.running = True

        self.state = self.STATE_INTRO
        self.intro = StarlightCrossingIntro()
        self.gameplay = StarlightCrossingGridGame(
            game_mode=game_mode,
            difficulty=difficulty,
            standalone_debug=standalone_debug,
        )

        self.fade_frame = 0
        self.fade_duration = 70

        self.countdown_timer = 0
        self.countdown_total_frames = FPS * 4

    def run(self):
        """Runs the standalone demo loop."""
        while self.running:
            self.handle_events()
            self.update()
            self.draw()

            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()

    def handle_events(self):
        """Handles standalone demo input."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False

                elif self.state == self.STATE_INTRO:
                    if event.key == pygame.K_SPACE and self.intro.frame >= 520:
                        self.state = self.STATE_FADE_TO_GAME
                        self.fade_frame = 0

                elif self.state == self.STATE_GAMEPLAY:
                    self.gameplay.handle_keydown(event.key)

    def update(self):
        """Updates the standalone demo state."""
        if self.state == self.STATE_INTRO:
            self.intro.update()

        elif self.state == self.STATE_FADE_TO_GAME:
            self.fade_frame += 1

            if self.fade_frame >= self.fade_duration:
                self.state = self.STATE_COUNTDOWN
                self.countdown_timer = 0

        elif self.state == self.STATE_COUNTDOWN:
            self.countdown_timer += 1

            if self.countdown_timer >= self.countdown_total_frames:
                self.state = self.STATE_GAMEPLAY

        elif self.state == self.STATE_GAMEPLAY:
            self.gameplay.update()

            if self.gameplay.is_complete():
                self.running = False

    def draw_countdown_overlay(self, screen):
        """Draws a short countdown before Starlight Crossing begins."""
        countdown_second = self.countdown_timer // FPS

        if countdown_second == 0:
            message = "3"
        elif countdown_second == 1:
            message = "2"
        elif countdown_second == 2:
            message = "1"
        else:
            message = "GO!"

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 95))
        screen.blit(overlay, (0, 0))

        pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.012)

        draw_soft_glow(
            screen,
            (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2),
            int(120 + pulse * 25),
            SOFT_GOLD,
            90,
        )

        draw_text_center(
            screen,
            message,
            self.gameplay.font_timer,
            SOFT_GOLD,
            (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2),
            alpha=255,
            shadow=True,
        )

        draw_text_center(
            screen,
            "Get ready...",
            self.gameplay.font_small,
            WHITE,
            (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 70),
            alpha=230,
            shadow=True,
        )

    def draw(self):
        """Draws the current standalone demo state."""
        if self.state == self.STATE_INTRO:
            self.intro.draw(self.screen)

        elif self.state == self.STATE_FADE_TO_GAME:
            self.intro.draw(self.screen)

            fade_t = min(self.fade_frame / self.fade_duration, 1.0)
            alpha = int(255 * ease_in_out(fade_t))
            self.gameplay.draw(self.screen, alpha=alpha)

        elif self.state == self.STATE_COUNTDOWN:
            self.gameplay.draw(self.screen, alpha=255)
            self.draw_countdown_overlay(self.screen)

        elif self.state == self.STATE_GAMEPLAY:
            self.gameplay.draw(self.screen, alpha=255)


if __name__ == "__main__":
    TransitionApp(
        game_mode=MODE_SINGLE_PLAYER,
        difficulty=DIFFICULTY_MEDIUM_HARD,
        standalone_debug=False,
    ).run()
