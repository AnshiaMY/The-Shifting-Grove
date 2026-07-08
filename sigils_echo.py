"""
sigils_echo.py

The Sigil's Echo mini-game for The Shifting Grove.

This module implements a memory-pattern challenge that can run as part of the
main maze game or independently as a standalone demo. The explorer and fox
compete by repeating glowing directional sequences. After the rounds finish, the
winner selects a reward, and game.py applies that reward to the main maze state.

This file owns The Sigil's Echo's internal systems:
- intro and instruction flow
- pattern generation
- player and fox input handling
- single-player fox simulation
- round scoring
- reward selection
- completion state

game.py is responsible for starting this mini-game, updating and drawing it
while the maze is paused, and applying the selected reward after completion.
"""

from pathlib import Path
import math
import random
import pygame

# Fallback imports let this mini-game run independently for local demos.
try:
    from asset_loader import load_image
except ImportError:
    def load_image(path, size=None, use_alpha=True):
        """Loads images when the shared asset loader is unavailable."""
        try:
            image = pygame.image.load(str(path))
            image = image.convert_alpha() if use_alpha else image.convert()

            if size is not None:
                image = pygame.transform.smoothscale(image, size)

            return image
        except Exception:
            return None


try:
    from settings import LOCAL_MULTIPLAYER, SINGLE_PLAYER
except ImportError:
    SINGLE_PLAYER = "single_player"
    LOCAL_MULTIPLAYER = "local_multiplayer"


try:
    import settings
except ImportError:
    class _FallbackSettings:
        SCREEN_WIDTH = 1024
        SCREEN_HEIGHT = 768
        FPS = 60
        IMAGE_DIR = Path("assets/images")
        FANTASY_FONT = Path("assets/fonts/fantasy_font.ttf")

    settings = _FallbackSettings()


# -----------------------------
# Shared settings and asset paths
# -----------------------------

SCREEN_WIDTH = getattr(settings, "SCREEN_WIDTH", 1024)
SCREEN_HEIGHT = getattr(settings, "SCREEN_HEIGHT", 768)
FPS = getattr(settings, "FPS", 60)

IMAGE_DIR = getattr(settings, "IMAGE_DIR", Path("assets/images"))
FANTASY_FONT = getattr(settings, "FANTASY_FONT", Path("assets/fonts/fantasy_font.ttf"))

WALL_IMAGE = getattr(settings, "WALL_IMAGE", IMAGE_DIR / "wall.png")
ECHO_SIGIL_IMAGE = getattr(settings, "ECHO_SIGIL_IMAGE", IMAGE_DIR / "echo_sigil.png")

SIGIL_INTRO_OVERLAY_IMAGE = getattr(
    settings,
    "SIGIL_INTRO_OVERLAY_IMAGE",
    IMAGE_DIR / "sigil_intro_overlay.png",
)

SIGIL_GAMEPLAY_BACKGROUND_IMAGE = getattr(
    settings,
    "SIGIL_GAMEPLAY_BACKGROUND_IMAGE",
    IMAGE_DIR / "sigil_gameplay_background.png",
)

SIGILS_REWARD_HUMAN_SELECT_IMAGE = getattr(
    settings,
    "SIGILS_REWARD_HUMAN_SELECT_IMAGE",
    IMAGE_DIR / "sigils_reward_human_select.png",
)

SIGILS_REWARD_FOX_SELECT_IMAGE = getattr(
    settings,
    "SIGILS_REWARD_FOX_SELECT_IMAGE",
    IMAGE_DIR / "sigils_reward_fox_select.png",
)

SIGILS_REWARD_GROVE_CALM_IMAGE = getattr(
    settings,
    "SIGILS_REWARD_GROVE_CALM_IMAGE",
    IMAGE_DIR / "sigils_reward_grove_calm.png",
)

SIGILS_REWARD_LANTERN_SHIELD_IMAGE = getattr(
    settings,
    "SIGILS_REWARD_LANTERN_SHIELD_IMAGE",
    IMAGE_DIR / "sigils_reward_lantern_shield.png",
)

SIGILS_REWARD_FOX_BANISH_IMAGE = getattr(
    settings,
    "SIGILS_REWARD_FOX_BANISH_IMAGE",
    IMAGE_DIR / "sigils_reward_fox_banish.png",
)

SIGILS_REWARD_MISCHIEF_SURGE_IMAGE = getattr(
    settings,
    "SIGILS_REWARD_MISCHIEF_SURGE_IMAGE",
    IMAGE_DIR / "sigils_reward_mischief_surge.png",
)

SIGILS_REWARD_SHADOW_RUSH_IMAGE = getattr(
    settings,
    "SIGILS_REWARD_SHADOW_RUSH_IMAGE",
    IMAGE_DIR / "sigils_reward_shadow_rush.png",
)

SIGILS_REWARD_PORTAL_FLICKER_IMAGE = getattr(
    settings,
    "SIGILS_REWARD_PORTAL_FLICKER_IMAGE",
    IMAGE_DIR / "sigils_reward_portal_flicker.png",
)

SIGILS_ECHO_COMPLETE_IMAGE = getattr(
    settings,
    "SIGILS_ECHO_COMPLETE_IMAGE",
    IMAGE_DIR / "sigils_echo_complete.png",
)

PLAYER_IMAGE = getattr(settings, "PLAYER_IMAGE", IMAGE_DIR / "player.png")
FOX_IMAGE = getattr(settings, "FOX_IMAGE", IMAGE_DIR / "fox.png")

SIGIL_ARROW_UP_IMAGE = getattr(settings, "SIGIL_ARROW_UP_IMAGE", IMAGE_DIR / "sigil_arrow_up.png")
SIGIL_ARROW_DOWN_IMAGE = getattr(settings, "SIGIL_ARROW_DOWN_IMAGE", IMAGE_DIR / "sigil_arrow_down.png")
SIGIL_ARROW_LEFT_IMAGE = getattr(settings, "SIGIL_ARROW_LEFT_IMAGE", IMAGE_DIR / "sigil_arrow_left.png")
SIGIL_ARROW_RIGHT_IMAGE = getattr(settings, "SIGIL_ARROW_RIGHT_IMAGE", IMAGE_DIR / "sigil_arrow_right.png")

HOURGLASS_FULL_IMAGE = getattr(
    settings,
    "HOURGLASS_FULL_IMAGE",
    IMAGE_DIR / "hourglass_full.png",
)

HOURGLASS_EMPTY_IMAGE = getattr(
    settings,
    "HOURGLASS_EMPTY_IMAGE",
    IMAGE_DIR / "hourglass_empty.png",
)

# -----------------------------
# Shared reward IDs returned to game.py
# -----------------------------

REWARD_GROVE_CALM = "grove_calm"
REWARD_LANTERN_SHIELD = "lantern_shield"
REWARD_FOX_BANISH = "fox_banish"
REWARD_MISCHIEF_SURGE = "mischief_surge"
REWARD_SHADOW_RUSH = "shadow_rush"
REWARD_PORTAL_FLICKER = "portal_flicker"

HUMAN_REWARDS = [
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


# -----------------------------
# Phases
# -----------------------------

PHASE_WALL_TRANSITION = "wall_transition"
PHASE_TITLE_REVEAL = "title_reveal"
PHASE_GAMEPLAY_FADE = "gameplay_fade"
PHASE_LISTEN_HOLD = "listen_hold"
PHASE_COUNTDOWN = "countdown"
PHASE_SHOW_PATTERN = "show_pattern"
PHASE_INPUT = "input"
PHASE_ROUND_RESULT = "round_result"
PHASE_WIN_SEQUENCE = "win_sequence"
PHASE_REWARD_SELECT = "reward_select"
PHASE_REWARD_TO_CLAIMED = "reward_to_claimed"
PHASE_REWARD_CLAIMED = "reward_claimed"
PHASE_COMPLETE = "complete"


# -----------------------------
# Winners
# -----------------------------

WINNER_HUMAN = "human"
WINNER_FOX = "fox"
WINNER_DRAW = "draw"


class StoneTheme:
    """Simple wall-based intro theme."""
    BACKGROUND = (28, 28, 30)

    TEXT = (58, 45, 30)
    TEXT_SOFT = (90, 75, 52)
    TEXT_DARK = (36, 28, 18)

    GLOW = (255, 245, 220)
    DUST = (232, 225, 203)

    VEIL = (245, 239, 224)
    DARK_OVERLAY = (0, 0, 0)


class GameTheme:
    """Gameplay screen colors selected to work with the forest-shrine background."""
    TEXT = (42, 45, 32)
    TEXT_SOFT = (72, 78, 58)
    TEXT_LIGHT = (248, 241, 214)

    HUMAN = (63, 166, 140)
    FOX = (130, 86, 190)

    EMPTY_CIRCLE = (235, 225, 185)
    CIRCLE_BORDER = (71, 77, 55)
    FILLED_CIRCLE = (72, 115, 88)

    DIRECTION_PURPLE = (200, 111, 55)
    DIRECTION_PURPLE_DARK = (120, 62, 34)

    TIMER = (84, 64, 30)
    SOFT_DARK = (0, 0, 0)


class SigilsEcho:
    """
    Controller for The Sigil's Echo mini-game.

    The constructor accepts optional font arguments so the mini-game works both
    when embedded in game.py and when run independently as a standalone demo.
    """

    WALL_TRANSITION_FRAMES = 120
    TITLE_REVEAL_TOTAL_FRAMES = 360
    GAMEPLAY_FADE_FRAMES = 90
    LISTEN_HOLD_FRAMES = 120
    COUNTDOWN_READY_FRAMES = 75
    COUNTDOWN_NUMBER_FRAMES = 60

    WIN_SEQUENCE_FRAMES = 180
    REWARD_TRANSITION_FRAMES = 60
    COMPLETE_TRANSITION_FRAMES = 60
    REWARD_TO_CLAIMED_FRAMES = 60
    REWARD_CLAIMED_HOLD_FRAMES = 210
    CLAIMED_TO_COMPLETE_FADE_FRAMES = 60
    AI_REWARD_PREVIEW_FRAMES = 300
    COMPLETE_HOLD_FRAMES = 180

    ROUNDS = 3
    ROUND_SECONDS = 5

    SYMBOL_SHOW_MS = 950
    SYMBOL_GAP_MS = 260
    REVEAL_END_PAUSE_MS = 650

    ROUND_RESULT_FRAMES = 130

    DIRECTIONS = ["UP", "DOWN", "LEFT", "RIGHT"]

    HUMAN_KEYS = {
        pygame.K_w: "UP",
        pygame.K_s: "DOWN",
        pygame.K_a: "LEFT",
        pygame.K_d: "RIGHT",
    }

    FOX_KEYS = {
        pygame.K_UP: "UP",
        pygame.K_DOWN: "DOWN",
        pygame.K_LEFT: "LEFT",
        pygame.K_RIGHT: "RIGHT",
    }

    def __init__(
        self,
        game_mode=SINGLE_PLAYER,
        large_font=None,
        medium_font=None,
        small_font=None,
        tiny_font=None,
    ):
        pygame.init()

        self.game_mode = game_mode

        self.phase = PHASE_WALL_TRANSITION
        self.wall_timer = 0
        self.title_timer = 0
        self.fade_timer = 0
        self.listen_hold_timer = 0
        self.countdown_timer = 0
        self.countdown_number = 3

        self.ready_to_continue = False

        # Use the fantasy font when available; load_fantasy_font handles fallback.
        self.title_font = self.load_fantasy_font(68)
        self.subtitle_font = self.load_fantasy_font(34)
        self.body_font = self.load_fantasy_font(24)
        self.small_font = self.load_fantasy_font(20)
        self.timer_font = self.load_fantasy_font(72)
        self.echo_now_font = self.load_fantasy_font(34)
        self.result_font = self.load_fantasy_font(36)
        self.win_font = self.load_fantasy_font(48)
        self.complete_font = self.load_fantasy_font(44)
        self.reward_font = self.load_fantasy_font(26)
        self.reward_small_font = self.load_fantasy_font(20)
        self.round_font = self.load_fantasy_font(28)

        self.wall_tile_image = load_image(WALL_IMAGE, (96, 96), use_alpha=True)

        self.echo_sigil_image = load_image(
            ECHO_SIGIL_IMAGE,
            (150, 150),
            use_alpha=True,
        )

        self.intro_overlay_image = load_image(
            SIGIL_INTRO_OVERLAY_IMAGE,
            (SCREEN_WIDTH, SCREEN_HEIGHT),
            use_alpha=True,
        )

        self.gameplay_background_image = load_image(
            SIGIL_GAMEPLAY_BACKGROUND_IMAGE,
            (SCREEN_WIDTH, SCREEN_HEIGHT),
            use_alpha=True,
        )

        raw_player_image = load_image(PLAYER_IMAGE, use_alpha=True)
        raw_fox_image = load_image(FOX_IMAGE, use_alpha=True)

        self.reward_select_images = {
            WINNER_HUMAN: self.load_fullscreen_ui_image(SIGILS_REWARD_HUMAN_SELECT_IMAGE),
            WINNER_FOX: self.load_fullscreen_ui_image(SIGILS_REWARD_FOX_SELECT_IMAGE),
        }

        self.reward_chosen_images = {
            REWARD_GROVE_CALM: self.load_fullscreen_ui_image(SIGILS_REWARD_GROVE_CALM_IMAGE),
            REWARD_LANTERN_SHIELD: self.load_fullscreen_ui_image(SIGILS_REWARD_LANTERN_SHIELD_IMAGE),
            REWARD_FOX_BANISH: self.load_fullscreen_ui_image(SIGILS_REWARD_FOX_BANISH_IMAGE),
            REWARD_MISCHIEF_SURGE: self.load_fullscreen_ui_image(SIGILS_REWARD_MISCHIEF_SURGE_IMAGE),
            REWARD_SHADOW_RUSH: self.load_fullscreen_ui_image(SIGILS_REWARD_SHADOW_RUSH_IMAGE),
            REWARD_PORTAL_FLICKER: self.load_fullscreen_ui_image(SIGILS_REWARD_PORTAL_FLICKER_IMAGE),
        }

        self.complete_screen_image = self.load_fullscreen_ui_image(SIGILS_ECHO_COMPLETE_IMAGE)

        self.player_image = self.scale_image_to_height(raw_player_image, 118)
        self.fox_image = self.scale_image_to_height(raw_fox_image, 108)

        self.arrow_images = {
            "UP": load_image(SIGIL_ARROW_UP_IMAGE, (185, 185), use_alpha=True),
            "DOWN": load_image(SIGIL_ARROW_DOWN_IMAGE, (185, 185), use_alpha=True),
            "LEFT": load_image(SIGIL_ARROW_LEFT_IMAGE, (185, 185), use_alpha=True),
            "RIGHT": load_image(SIGIL_ARROW_RIGHT_IMAGE, (185, 185), use_alpha=True),
        }

        raw_hourglass_full = load_image(HOURGLASS_FULL_IMAGE, use_alpha=True)
        raw_hourglass_empty = load_image(HOURGLASS_EMPTY_IMAGE, use_alpha=True)

        self.hourglass_full_image = (
            pygame.transform.smoothscale(raw_hourglass_full, (70, 70))
            if raw_hourglass_full else None
        )

        self.hourglass_empty_image = (
            pygame.transform.smoothscale(raw_hourglass_empty, (70, 70))
            if raw_hourglass_empty else None
        )


        self.particles = self.create_particles(48)

        # Gameplay state.
        self.round_number = 1
        self.pattern = []
        self.human_progress = 0
        self.fox_progress = 0
        self.human_score = 0
        self.fox_score = 0

        # Main maze context passed in from game.py.
        self.portal_active = False
        self.grove_shift_meter = 0
        self.shards_collected = 0
        self.fox_urgency = 0

        self.human_completed_time = None
        self.fox_completed_time = None
        self.round_winner = None
        self.round_message = ""

        self.reveal_start_ticks = 0
        self.input_start_ticks = 0
        self.round_result_timer = 0

        self.ai_will_succeed = False
        self.ai_completion_ms = None

        # Reward state returned to game.py after the mini-game completes.
        self.selected_reward = None
        self.final_winner = None
        self.reward_options = []
        self.reward_claimed_timer = 0
        self.reward_to_claimed_timer = 0
        self.win_sequence_timer = 0
        self.win_sequence_message = ""
        self.reward_transition_timer = 0
        self.ai_reward_preview_timer = 0
        self.complete_transition_timer = 0
        self.complete_hold_timer = 0
        self.mini_game_finished = False

    # -----------------------------
    # Setup helpers
    # -----------------------------

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

    def load_fullscreen_ui_image(self, path):
        """Loads a full-screen reward/complete UI image."""
        image = load_image(path, use_alpha=True)

        if image is None:
            return None

        return pygame.transform.smoothscale(image, (SCREEN_WIDTH, SCREEN_HEIGHT))

    def load_fantasy_font(self, size):
        """Loads the project's fantasy font only."""
        if FANTASY_FONT and Path(FANTASY_FONT).exists():
            return pygame.font.Font(str(FANTASY_FONT), size)

        return pygame.font.Font(None, size)

    def create_particles(self, count):
        """Creates small floating dust particles."""
        particles = []

        for _ in range(count):
            particles.append(
                {
                    "x": random.randint(0, SCREEN_WIDTH),
                    "y": random.randint(0, SCREEN_HEIGHT),
                    "speed": random.uniform(0.08, 0.22),
                    "radius": random.randint(1, 2),
                    "phase": random.uniform(0, math.tau),
                }
            )

        return particles

    # -----------------------------
    # Input
    # -----------------------------

    def handle_event(self, event):
        """Handles keyboard input."""
        if event.type != pygame.KEYDOWN:
            return

        if self.phase == PHASE_TITLE_REVEAL and event.key == pygame.K_SPACE:
            self.ready_to_continue = True
            self.phase = PHASE_GAMEPLAY_FADE
            self.fade_timer = 0
            return

        if self.phase == PHASE_INPUT:
            self.handle_pattern_key(event.key)

        if self.phase == PHASE_REWARD_SELECT:
            self.handle_reward_key(event.key)

    def handle_reward_key(self, key):
        """Lets the winning side choose a reward."""
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
        self.phase = PHASE_REWARD_TO_CLAIMED
        self.reward_to_claimed_timer = 0
        self.reward_claimed_timer = 0

    def handle_pattern_key(self, key):
        """Processes human and fox pattern input."""
        if key in self.HUMAN_KEYS:
            self.process_human_direction(self.HUMAN_KEYS[key])

        if self.game_mode == LOCAL_MULTIPLAYER and key in self.FOX_KEYS:
            self.process_fox_direction(self.FOX_KEYS[key])

    def process_human_direction(self, direction):
        """Checks one human input against the pattern."""
        if self.human_completed_time is not None:
            return

        if not self.pattern:
            return

        expected_direction = self.pattern[self.human_progress]

        if direction == expected_direction:
            self.human_progress += 1

            if self.human_progress >= len(self.pattern):
                self.human_completed_time = self.get_input_elapsed_ms()
        else:
            self.human_progress = 0

    def process_fox_direction(self, direction):
        """Checks one local-multiplayer fox input against the pattern."""
        if self.fox_completed_time is not None:
            return

        if not self.pattern:
            return

        expected_direction = self.pattern[self.fox_progress]

        if direction == expected_direction:
            self.fox_progress += 1

            if self.fox_progress >= len(self.pattern):
                self.fox_completed_time = self.get_input_elapsed_ms()
        else:
            self.fox_progress = 0

    # -----------------------------
    # Update
    # -----------------------------

    def update(self, portal_is_active=False, grove_shift_meter=0):
        """
        Updates the current phase.

        game.py passes current maze context into the mini-game so the fox reward
        logic can react to portal and Grove Shift pressure.
        """
        self.update_particles()
        self.portal_active = portal_is_active
        self.grove_shift_meter = grove_shift_meter

        if self.phase == PHASE_WALL_TRANSITION:
            self.wall_timer += 1

            if self.wall_timer >= self.WALL_TRANSITION_FRAMES:
                self.phase = PHASE_TITLE_REVEAL
                self.title_timer = 0

        elif self.phase == PHASE_TITLE_REVEAL:
            self.title_timer += 1

        elif self.phase == PHASE_GAMEPLAY_FADE:
            self.fade_timer += 1

            if self.fade_timer >= self.GAMEPLAY_FADE_FRAMES:
                self.phase = PHASE_LISTEN_HOLD
                self.listen_hold_timer = 0

        elif self.phase == PHASE_LISTEN_HOLD:
            self.listen_hold_timer += 1

            if self.listen_hold_timer >= self.LISTEN_HOLD_FRAMES:
                self.start_countdown()

        elif self.phase == PHASE_COUNTDOWN:
            self.update_countdown()

        elif self.phase == PHASE_SHOW_PATTERN:
            self.update_show_pattern_phase()

        elif self.phase == PHASE_INPUT:
            self.update_input_phase()

        elif self.phase == PHASE_ROUND_RESULT:
            self.update_round_result_phase()

        elif self.phase == PHASE_WIN_SEQUENCE:
            self.update_win_sequence()

        elif self.phase == PHASE_REWARD_SELECT:
            if self.reward_transition_timer < self.REWARD_TRANSITION_FRAMES:
                self.reward_transition_timer += 1

            if self.game_mode == SINGLE_PLAYER and self.final_winner == WINNER_FOX:
                self.ai_reward_preview_timer += 1

                if self.ai_reward_preview_timer >= self.AI_REWARD_PREVIEW_FRAMES:
                    self.selected_reward = self.choose_ai_fox_reward()
                    self.phase = PHASE_REWARD_TO_CLAIMED
                    self.reward_to_claimed_timer = 0
                    self.reward_claimed_timer = 0

        elif self.phase == PHASE_REWARD_TO_CLAIMED:
            self.reward_to_claimed_timer += 1

            if self.reward_to_claimed_timer >= self.REWARD_TO_CLAIMED_FRAMES:
                self.phase = PHASE_REWARD_CLAIMED
                self.reward_claimed_timer = 0

        elif self.phase == PHASE_REWARD_CLAIMED:
            self.reward_claimed_timer += 1

            if self.reward_claimed_timer >= self.REWARD_CLAIMED_HOLD_FRAMES:
                self.phase = PHASE_COMPLETE
                self.complete_transition_timer = 0
                self.complete_hold_timer = 0
                self.mini_game_finished = False

        elif self.phase == PHASE_COMPLETE:
            self.complete_hold_timer += 1

            if self.complete_hold_timer >= self.COMPLETE_HOLD_FRAMES:
                self.mini_game_finished = True

    def update_particles(self):
        """Updates subtle drifting particles."""
        for particle in self.particles:
            particle["y"] -= particle["speed"]
            particle["x"] += math.sin(
                pygame.time.get_ticks() * 0.001 + particle["phase"]
            ) * 0.08

            if particle["y"] < -10:
                particle["y"] = SCREEN_HEIGHT + 10
                particle["x"] = random.randint(0, SCREEN_WIDTH)


    def start_countdown(self):
        """Starts the ready countdown before the first pattern appears."""
        self.phase = PHASE_COUNTDOWN
        self.countdown_timer = 0
        self.countdown_number = 3

    def update_countdown(self):
        """Updates the Are You Ready / 3 / 2 / 1 countdown."""
        self.countdown_timer += 1

        ready_phase_total = self.COUNTDOWN_READY_FRAMES

        if self.countdown_timer < ready_phase_total:
            return

        number_elapsed = self.countdown_timer - ready_phase_total
        current_step = number_elapsed // self.COUNTDOWN_NUMBER_FRAMES

        self.countdown_number = 3 - current_step

        if self.countdown_number <= 0:
            self.start_round()

    def start_round(self):
        """Starts a new memory round."""
        self.phase = PHASE_SHOW_PATTERN

        pattern_length = self.round_number + 2
        self.pattern = [random.choice(self.DIRECTIONS) for _ in range(pattern_length)]

        self.human_progress = 0
        self.fox_progress = 0
        self.human_completed_time = None
        self.fox_completed_time = None
        self.round_winner = None
        self.round_message = ""

        self.reveal_start_ticks = pygame.time.get_ticks()
        self.input_start_ticks = 0
        self.round_result_timer = 0

        self.setup_ai_fox_round()

    def setup_ai_fox_round(self):
        """
        Decides whether the AI fox completes this round.

        The fox becomes more accurate and faster when the main maze situation says
        it is losing or the player is close to escaping.
        """
        if self.game_mode != SINGLE_PLAYER:
            self.ai_will_succeed = False
            self.ai_completion_ms = None
            return

        fox_urgency = max(0, min(100, getattr(self, "fox_urgency", 0)))

        if self.round_number == 1:
            success_chance = 0.72
        elif self.round_number == 2:
            success_chance = 0.64
        else:
            success_chance = 0.56

        # Main-game urgency makes the fox focus harder.
        if fox_urgency >= 80:
            success_chance += 0.22
        elif fox_urgency >= 60:
            success_chance += 0.15
        elif fox_urgency >= 40:
            success_chance += 0.08

        # If the portal is active, the fox is desperate to stop the escape.
        if getattr(self, "portal_active", False):
            success_chance += 0.08

        # Keep it fair. The fox should be strong, not impossible.
        success_chance = max(0.20, min(0.82, success_chance))

        self.ai_will_succeed = random.random() <= success_chance

        if not self.ai_will_succeed:
            self.ai_completion_ms = None
            return

        # Higher urgency means the fox answers faster.
        if fox_urgency >= 80:
            min_time = 1150
            max_time = 2900
        elif fox_urgency >= 60:
            min_time = 1300
            max_time = 3400
        elif fox_urgency >= 40:
            min_time = 1450
            max_time = 3800
        else:
            min_time = 1600
            max_time = 4300

        self.ai_completion_ms = random.randint(min_time, max_time)

    def update_show_pattern_phase(self):
        """Reveals the pattern, then starts input."""
        if self.get_reveal_elapsed_ms() >= self.get_total_reveal_duration_ms():
            self.phase = PHASE_INPUT
            self.input_start_ticks = pygame.time.get_ticks()

    def update_input_phase(self):
        """Updates the timed input phase."""
        if self.game_mode == SINGLE_PLAYER:
            self.update_ai_fox_progress()

        both_completed = (
            self.human_completed_time is not None
            and self.fox_completed_time is not None
        )

        time_expired = self.get_input_elapsed_ms() >= self.ROUND_SECONDS * 1000

        if both_completed or time_expired:
            self.finish_round()

    def update_ai_fox_progress(self):
        """Simulates AI fox progress."""
        if not self.ai_will_succeed or self.ai_completion_ms is None:
            return

        if self.fox_completed_time is not None:
            return

        elapsed = self.get_input_elapsed_ms()
        progress_ratio = min(elapsed / max(self.ai_completion_ms, 1), 1)
        self.fox_progress = min(len(self.pattern), int(progress_ratio * len(self.pattern)))

        if elapsed >= self.ai_completion_ms:
            self.fox_progress = len(self.pattern)
            self.fox_completed_time = self.ai_completion_ms

    def finish_round(self):
        """Determines the winner of the round."""
        if self.human_completed_time is not None and self.fox_completed_time is not None:
            if self.human_completed_time < self.fox_completed_time:
                self.round_winner = WINNER_HUMAN
            elif self.fox_completed_time < self.human_completed_time:
                self.round_winner = WINNER_FOX
            else:
                self.round_winner = WINNER_DRAW

        elif self.human_completed_time is not None:
            self.round_winner = WINNER_HUMAN

        elif self.fox_completed_time is not None:
            self.round_winner = WINNER_FOX

        else:
            self.round_winner = WINNER_DRAW

        if self.round_winner == WINNER_HUMAN:
            self.human_score += 1
            self.round_message = ["The explorer", "answered first"]
        elif self.round_winner == WINNER_FOX:
            self.fox_score += 1
            self.round_message = ["The fox", "answered first"]
        else:
            self.round_message = ["The echo was", "unanswered"]

        self.phase = PHASE_ROUND_RESULT
        self.round_result_timer = 0

    def update_round_result_phase(self):
        """Shows round result, then advances."""
        self.round_result_timer += 1

        if self.round_result_timer < self.ROUND_RESULT_FRAMES:
            return

        if self.round_number < self.ROUNDS:
            self.round_number += 1
            self.start_round()
        else:
            self.start_win_sequence()

    # -----------------------------
    # Public helpers
    # -----------------------------

    def is_complete(self):
        """Returns True once the final complete screen has shown long enough."""
        return self.mini_game_finished

    def get_selected_reward(self):
        """Returns the selected reward ID for game.py."""
        return self.selected_reward

    def get_final_winner(self):
        """Returns the final winner of the mini-game."""
        if self.final_winner is not None:
            return self.final_winner

        if self.human_score > self.fox_score:
            return WINNER_HUMAN

        if self.fox_score > self.human_score:
            return WINNER_FOX

        return WINNER_DRAW

    # -----------------------------
    # Timing helpers
    # -----------------------------

    def get_reveal_elapsed_ms(self):
        """Returns elapsed pattern reveal time."""
        return pygame.time.get_ticks() - self.reveal_start_ticks

    def get_input_elapsed_ms(self):
        """Returns elapsed input time."""
        return pygame.time.get_ticks() - self.input_start_ticks

    def get_seconds_remaining(self):
        """Returns input time remaining."""
        round_ms = self.ROUND_SECONDS * 1000
        return max(0, round_ms - self.get_input_elapsed_ms()) / 1000

    def get_total_reveal_duration_ms(self):
        """Returns total pattern reveal duration."""
        return (
            len(self.pattern) * self.SYMBOL_SHOW_MS
            + max(0, len(self.pattern) - 1) * self.SYMBOL_GAP_MS
            + self.REVEAL_END_PAUSE_MS
        )

    def get_reveal_active_index(self):
        """Returns the currently flashing pattern index."""
        elapsed = self.get_reveal_elapsed_ms()
        slot_duration = self.SYMBOL_SHOW_MS + self.SYMBOL_GAP_MS

        for index in range(len(self.pattern)):
            start = index * slot_duration
            end = start + self.SYMBOL_SHOW_MS

            if start <= elapsed < end:
                return index

        return None

    # -----------------------------
    # Draw entry
    # -----------------------------

    def draw(self, screen):
        """Draws the current state."""
        if self.phase == PHASE_WALL_TRANSITION:
            self.draw_wall_transition(screen)

        elif self.phase == PHASE_TITLE_REVEAL:
            self.draw_title_screen(screen)

        elif self.phase == PHASE_GAMEPLAY_FADE:
            self.draw_intro_to_gameplay_fade(screen)

        elif self.phase == PHASE_LISTEN_HOLD:
            self.draw_gameplay_screen(screen)

        elif self.phase == PHASE_COUNTDOWN:
            self.draw_countdown_screen(screen)

        elif self.phase in (
            PHASE_SHOW_PATTERN,
            PHASE_INPUT,
            PHASE_ROUND_RESULT,
            PHASE_WIN_SEQUENCE,
            PHASE_REWARD_SELECT,
            PHASE_REWARD_TO_CLAIMED,
            PHASE_REWARD_CLAIMED,
        ):
            self.draw_gameplay_screen(screen)

        elif self.phase == PHASE_COMPLETE:
            self.draw_echo_complete_screen(screen)

    # -----------------------------
    # Wall / intro drawing
    # -----------------------------

    def draw_wall_transition(self, screen):
        """Draws rotating wall tiles that settle into the screen."""
        self.draw_wall_background(screen)

        progress = min(self.wall_timer / self.WALL_TRANSITION_FRAMES, 1.0)
        eased = self.ease_out_cubic(progress)

        tile_size = 96
        cols = int(SCREEN_WIDTH / tile_size) + 3
        rows = int(SCREEN_HEIGHT / tile_size) + 3

        for row in range(rows):
            for col in range(cols):
                delay = (row + col) / (rows + cols)
                local_progress = max(0.0, min((eased - delay * 0.42) / 0.58, 1.0))

                if local_progress <= 0:
                    continue

                x = col * tile_size - tile_size
                y = row * tile_size - tile_size

                angle = 280 * (1 - local_progress)
                scale = 0.45 + local_progress * 0.65
                alpha = int(255 * local_progress)

                if self.wall_tile_image:
                    tile = pygame.transform.rotozoom(self.wall_tile_image, angle, scale)
                    tile.set_alpha(alpha)
                    rect = tile.get_rect(center=(x + tile_size // 2, y + tile_size // 2))
                    screen.blit(tile, rect)
                else:
                    size = int(tile_size * scale)
                    surface = pygame.Surface((size, size), pygame.SRCALPHA)
                    surface.fill((90, 90, 100, alpha))
                    rotated = pygame.transform.rotate(surface, angle)
                    rect = rotated.get_rect(center=(x + tile_size // 2, y + tile_size // 2))
                    screen.blit(rotated, rect)

    def draw_title_screen(self, screen):
        """Draws the wall background, logo, title, and instructions."""
        self.draw_wall_background(screen)
        self.draw_particles(screen)

        progress = min(self.title_timer / self.TITLE_REVEAL_TOTAL_FRAMES, 1.0)
        overlay_alpha = int(255 * min(progress / 0.35, 1.0))

        if self.intro_overlay_image:
            overlay = self.intro_overlay_image.copy()
            overlay.set_alpha(overlay_alpha)
            screen.blit(overlay, (0, 0))

        veil = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        veil.fill((*StoneTheme.VEIL, 12))
        screen.blit(veil, (0, 0))

        logo_alpha = int(255 * min(progress / 0.18, 1.0))
        title_alpha = int(255 * min(max(progress - 0.14, 0) / 0.18, 1.0))
        instructions_alpha = int(255 * min(max(progress - 0.32, 0) / 0.22, 1.0))
        prompt_alpha = int(255 * min(max(progress - 0.50, 0) / 0.18, 1.0))

        center_x = SCREEN_WIDTH // 2

        logo_center = (center_x, 128)

        if self.echo_sigil_image:
            logo = self.echo_sigil_image.copy()
            logo.set_alpha(logo_alpha)
            rect = logo.get_rect(center=logo_center)
            screen.blit(logo, rect)

        self.draw_text(
            screen,
            "The Sigil's Echo",
            self.title_font,
            StoneTheme.TEXT,
            (center_x, 250),
            center=True,
            alpha=title_alpha,
        )

        self.draw_text(
            screen,
            "A memory duel inside the shifting grove",
            self.subtitle_font,
            StoneTheme.TEXT_SOFT,
            (center_x, 305),
            center=True,
            alpha=title_alpha,
        )

        left_x = 292
        heading_y = 365
        start_y = 415
        line_spacing = 42

        self.draw_text(
            screen,
            "How to Play",
            self.subtitle_font,
            StoneTheme.TEXT,
            (left_x, heading_y),
            center=False,
            alpha=instructions_alpha,
        )

        instruction_lines = [
            "• Watch the grove's pattern.",
            "• Echo it back before the fox does.",
            "• Human uses W A S D.",
            "• Fox uses Arrow Keys or AI.",
            "• Best of 3 rounds wins the duel.",
        ]

        for i, line in enumerate(instruction_lines):
            self.draw_text(
                screen,
                line,
                self.body_font,
                StoneTheme.TEXT,
                (left_x, start_y + i * line_spacing),
                center=False,
                alpha=instructions_alpha,
            )

        self.draw_text(
            screen,
            "Press SPACE to continue",
            self.small_font,
            StoneTheme.TEXT_SOFT,
            (center_x, 675),
            center=True,
            alpha=prompt_alpha,
        )

    def draw_intro_to_gameplay_fade(self, screen):
        """Crossfades from the intro screen into the active gameplay background."""
        progress = min(self.fade_timer / max(self.GAMEPLAY_FADE_FRAMES, 1), 1.0)

        # Draw intro underneath.
        self.draw_title_screen(screen)

        # Fade gameplay screen over it.
        gameplay_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self.draw_gameplay_screen(gameplay_surface)

        gameplay_surface.set_alpha(int(255 * progress))
        screen.blit(gameplay_surface, (0, 0))

    def draw_wall_background(self, screen):
        """Draws a simple wall background."""
        screen.fill(StoneTheme.BACKGROUND)

        if self.wall_tile_image:
            tile = self.wall_tile_image.copy()
            tile.set_alpha(255)

            for row in range(0, SCREEN_HEIGHT, 96):
                for col in range(0, SCREEN_WIDTH, 96):
                    screen.blit(tile, (col, row))

        # Soft dark overlay so the text reads clearly.
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((*StoneTheme.DARK_OVERLAY, 90))
        screen.blit(overlay, (0, 0))

    def draw_particles(self, screen):
        """Draws subtle dust particles."""
        particle_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

        for particle in self.particles:
            flicker = 0.5 + 0.5 * math.sin(
                pygame.time.get_ticks() * 0.002 + particle["phase"]
            )

            color = (*StoneTheme.DUST, int(35 + 25 * flicker))

            pygame.draw.circle(
                particle_surface,
                color,
                (int(particle["x"]), int(particle["y"])),
                particle["radius"],
            )

        screen.blit(particle_surface, (0, 0))

    # -----------------------------
    # Gameplay drawing
    # -----------------------------

    def draw_countdown_screen(self, screen):
        """Draws the Are You Ready / 3 / 2 / 1 countdown screen."""
        self.draw_gameplay_background(screen)

        self.draw_text(
            screen,
            "The Sigil's Echo",
            self.subtitle_font,
            GameTheme.TEXT,
            (SCREEN_WIDTH // 2, 55),
            center=True,
        )

        self.draw_text(
            screen,
            f"Round {self.round_number} of {self.ROUNDS}",
            self.small_font,
            GameTheme.TEXT_SOFT,
            (SCREEN_WIDTH // 2, 100),
            center=True,
        )

        ready_phase_total = self.COUNTDOWN_READY_FRAMES

        if self.countdown_timer < ready_phase_total:
            main_text = "Are You Ready?"
            font = self.subtitle_font
            y = 360
        else:
            main_text = str(max(1, self.countdown_number))
            font = self.title_font
            y = 365

        self.draw_text(
            screen,
            main_text,
            font,
            GameTheme.TEXT,
            (SCREEN_WIDTH // 2, y),
            center=True,
        )


        self.draw_human_and_fox_status(screen)

    def draw_gameplay_screen(self, screen):
        """Draws the active memory-game screen."""
        if self.phase in (PHASE_REWARD_SELECT, PHASE_REWARD_TO_CLAIMED, PHASE_REWARD_CLAIMED):
            if self.phase == PHASE_REWARD_SELECT:
                self.draw_reward_select(screen)

            elif self.phase == PHASE_REWARD_TO_CLAIMED:
                self.draw_reward_to_claimed_transition(screen)

            else:
                self.draw_reward_claimed_to_complete_transition(screen)

            return

        self.draw_gameplay_background(screen)

        self.draw_text(
            screen,
            "The Sigil's Echo",
            self.subtitle_font,
            GameTheme.TEXT,
            (SCREEN_WIDTH // 2, 55),
            center=True,
        )

        self.draw_text(
            screen,
            f"Round {self.round_number} of {self.ROUNDS}",
            self.small_font,
            GameTheme.TEXT_SOFT,
            (SCREEN_WIDTH // 2, 100),
            center=True,
        )

        if self.phase == PHASE_SHOW_PATTERN:
            self.draw_pattern_reveal(screen)

        elif self.phase == PHASE_INPUT:
            self.draw_input_phase(screen)

        elif self.phase == PHASE_ROUND_RESULT:
            self.draw_round_result(screen)

        elif self.phase == PHASE_WIN_SEQUENCE:
            self.draw_win_sequence(screen)

        elif self.phase in (PHASE_GAMEPLAY_FADE, PHASE_LISTEN_HOLD, PHASE_COMPLETE):
            self.draw_idle_gameplay_layout(screen)

        if self.phase not in (
            PHASE_REWARD_SELECT,
            PHASE_REWARD_CLAIMED,
            PHASE_COMPLETE,
        ):
            self.draw_human_and_fox_status(screen)

    def draw_gameplay_background(self, screen):
        """Draws the generated forest-shrine gameplay background."""
        if self.gameplay_background_image:
            screen.blit(self.gameplay_background_image, (0, 0))
        else:
            self.draw_wall_background(screen)

        # Very soft readable layer; not a box.
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((255, 248, 220, 18))
        screen.blit(overlay, (0, 0))

    def draw_pattern_reveal(self, screen):
        """Draws the flashing arrow sequence."""
        active_index = self.get_reveal_active_index()

        if active_index is not None:
            direction = self.pattern[active_index]
            self.draw_arrow_image(screen, direction, (512, 350))

        self.draw_reveal_circles(screen, active_index)

    def draw_input_phase(self, screen):
        """Draws the timed input phase with a visual hourglass timer."""
        seconds = self.get_seconds_remaining()

        self.draw_timer_display(screen, seconds)

        self.draw_text(
            screen,
            "Echo now!",
            self.echo_now_font,
            GameTheme.TEXT_SOFT,
            (512, 425),
            center=True,
        )

    def draw_timer_display(self, screen, seconds):
        """Draws a larger timer with an animated hourglass in the center shrine area."""
        timer_center = (512, 350)

        # Alternate hourglass image to create a simple animated effect.
        flip_frame = (pygame.time.get_ticks() // 350) % 2

        if flip_frame == 0:
            hourglass = self.hourglass_full_image
        else:
            hourglass = self.hourglass_empty_image

        if hourglass:
            hourglass_rect = hourglass.get_rect(center=(timer_center[0] - 95, timer_center[1] + 4))
            screen.blit(hourglass, hourglass_rect)
        else:
            self.draw_text(
                screen,
                "⌛",
                self.subtitle_font,
                GameTheme.TIMER,
                (timer_center[0] - 95, timer_center[1]),
                center=True,
            )

        self.draw_text(
            screen,
            f"{seconds:.1f}",
            self.timer_font,
            GameTheme.TIMER,
            (timer_center[0] + 30, timer_center[1]),
            center=True,
        )

    def draw_round_result(self, screen):
        """Draws round result text in the center shrine circle."""
        center_x = 512
        start_y = 345
        line_spacing = 48

        if isinstance(self.round_message, list):
            lines = self.round_message
        else:
            lines = [self.round_message]

        for i, line in enumerate(lines):
            self.draw_text(
                screen,
                line,
                self.result_font,
                GameTheme.TEXT,
                (center_x, start_y + i * line_spacing),
                center=True,
            )

    def draw_idle_gameplay_layout(self, screen):
        """Draws a calm center message during non-interactive gameplay holds."""
        self.draw_text(
            screen,
            "Listen to the Echo...",
            self.result_font,
            GameTheme.TEXT_SOFT,
            (SCREEN_WIDTH // 2, 355),
            center=True,
        )

    def draw_arrow_image(self, screen, direction, center):
        """Draws a large arrow image in the center."""
        image = self.arrow_images.get(direction)

        if image:
            rect = image.get_rect(center=center)
            screen.blit(image, rect)
        else:
            fallback_text = {
                "UP": "W",
                "DOWN": "S",
                "LEFT": "A",
                "RIGHT": "D",
            }.get(direction, "?")

            self.draw_text(
                screen,
                fallback_text,
                self.title_font,
                GameTheme.TEXT,
                center,
                center=True,
            )

    def draw_reveal_circles(self, screen, active_index):
        """Draws pattern progress circles under the center arrow."""
        total = len(self.pattern)
        radius = 10
        gap = 28
        total_width = total * radius * 2 + (total - 1) * gap
        start_x = SCREEN_WIDTH // 2 - total_width // 2
        y = 585

        for index in range(total):
            center = (start_x + index * (radius * 2 + gap) + radius, y)

            if index == active_index:
                pygame.draw.circle(screen, GameTheme.DIRECTION_PURPLE, center, radius + 3)
                pygame.draw.circle(screen, GameTheme.DIRECTION_PURPLE_DARK, center, radius + 3, 2)
            else:
                pygame.draw.circle(screen, GameTheme.EMPTY_CIRCLE, center, radius)
                pygame.draw.circle(screen, GameTheme.DIRECTION_PURPLE_DARK, center, radius, 2)

    def draw_human_and_fox_status(self, screen):
        """Draws player and fox images inside the background's lower circles."""
        human_center = (190, 600)
        fox_center = (840, 600)

        self.draw_character_circle(
            screen,
            center=human_center,
            image=self.player_image,
            border_color=GameTheme.HUMAN,
        )

        self.draw_character_circle(
            screen,
            center=fox_center,
            image=self.fox_image,
            border_color=GameTheme.FOX,
        )

        self.draw_progress_circles(
            screen,
            total=len(self.pattern) if self.pattern else 3,
            completed=self.human_progress,
            center_x=human_center[0],
            y=692,
            fill_color=GameTheme.HUMAN,
        )

        self.draw_progress_circles(
            screen,
            total=len(self.pattern) if self.pattern else 3,
            completed=self.fox_progress,
            center_x=fox_center[0],
            y=692,
            fill_color=GameTheme.FOX,
        )

    def draw_character_circle(self, screen, center, image, border_color):
        """Draws the player or fox image inside a larger clean circle."""
        radius = 54

        pygame.draw.circle(screen, (245, 235, 198), center, radius)
        pygame.draw.circle(screen, border_color, center, radius, 4)

        if image:
            rect = image.get_rect(center=center)
            screen.blit(image, rect)
        else:
            pygame.draw.circle(screen, border_color, center, radius - 14)

    def draw_progress_circles(self, screen, total, completed, center_x, y, fill_color):
        """Draws small horizontal memory progress buttons."""
        radius = 10
        gap = 22
        total_width = total * radius * 2 + (total - 1) * gap
        start_x = center_x - total_width // 2

        for index in range(total):
            center = (start_x + index * (radius * 2 + gap) + radius, y)

            if index < completed:
                pygame.draw.circle(screen, fill_color, center, radius)
                pygame.draw.circle(screen, GameTheme.CIRCLE_BORDER, center, radius, 2)
            else:
                pygame.draw.circle(screen, GameTheme.EMPTY_CIRCLE, center, radius)
                pygame.draw.circle(screen, GameTheme.CIRCLE_BORDER, center, radius, 2)

    def draw_echo_complete_screen(self, screen, alpha=255):
        """Draws the final Echo Complete screen."""
        alpha = max(0, min(255, alpha))

        if self.complete_screen_image:
            image = self.complete_screen_image.copy()
            image.set_alpha(alpha)
            screen.blit(image, (0, 0))
            return

        # Fallback if the complete screen image is unavailable.
        self.draw_gameplay_background(screen)
        self.draw_text(
            screen,
            "Echo Complete",
            self.complete_font,
            GameTheme.TEXT,
            (512, 370),
            center=True,
            alpha=alpha,
        )

    # -----------------------------
    # General drawing helpers
    # -----------------------------

    def draw_text(self, screen, text, font, color, pos, center=False, alpha=255):
        """Draws text cleanly."""
        surface = font.render(text, True, color)
        surface.set_alpha(alpha)
        rect = surface.get_rect(center=pos) if center else surface.get_rect(topleft=pos)
        screen.blit(surface, rect)

    def ease_out_cubic(self, value):
        """Cubic easing."""
        value = max(0, min(value, 1))
        return 1 - pow(1 - value, 3)

    # -----------------------------
    # Rewards
    # -----------------------------

    def update_win_sequence(self):
        """Updates the winner reveal sequence."""
        self.win_sequence_timer += 1

        if self.win_sequence_timer >= self.WIN_SEQUENCE_FRAMES:
            if self.final_winner == WINNER_DRAW:
                self.selected_reward = None
                self.reward_options = []
                self.phase = PHASE_COMPLETE
                self.complete_transition_timer = 0
                self.complete_hold_timer = 0
                self.mini_game_finished = False
            else:
                self.start_reward_selection()

    def start_win_sequence(self):
        """Starts a short visual winner sequence before reward selection."""
        self.final_winner = self.get_final_winner()
        self.win_sequence_timer = 0

        if self.final_winner == WINNER_HUMAN:
            self.win_sequence_message = "The Explorer Wins"
        elif self.final_winner == WINNER_FOX:
            self.win_sequence_message = "The Fox Wins"
        else:
            self.win_sequence_message = "The Echo Is Tied"
            self.selected_reward = None

        self.phase = PHASE_WIN_SEQUENCE

    def draw_win_sequence(self, screen):
        """Draws a magical winner reveal before reward selection."""
        progress = min(self.win_sequence_timer / max(self.WIN_SEQUENCE_FRAMES, 1), 1.0)

        pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.008)

        if self.final_winner == WINNER_HUMAN:
            glow_color = GameTheme.HUMAN
        elif self.final_winner == WINNER_FOX:
            glow_color = GameTheme.FOX
        else:
            glow_color = GameTheme.DIRECTION_PURPLE

        # Soft glow in the center shrine circle.
        glow_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

        for radius in range(210, 40, -28):
            alpha = int((18 + 18 * pulse) * (radius / 210))
            pygame.draw.circle(
                glow_surface,
                (*glow_color, alpha),
                (512, 360),
                radius,
            )

        screen.blit(glow_surface, (0, 0))

        # Slight scale-in effect for the winner text.
        text_alpha = int(255 * min(progress / 0.35, 1.0))

        self.draw_text(
            screen,
            self.win_sequence_message,
            self.win_font,
            GameTheme.TEXT,
            (512, 345),
            center=True,
            alpha=text_alpha,
        )

        if self.final_winner == WINNER_DRAW:
            reward_message = "The grove offers no reward..."
        else:
            reward_message = "The grove offers a reward..."

        self.draw_text(
            screen,
            reward_message,
            self.reward_font,
            GameTheme.TEXT_SOFT,
            (512, 405),
            center=True,
            alpha=text_alpha,
        )

    def start_reward_selection(self):
        """Starts reward selection after all rounds are complete."""
        self.final_winner = self.get_final_winner()

        if self.final_winner == WINNER_HUMAN:
            self.reward_options = HUMAN_REWARDS
            self.phase = PHASE_REWARD_SELECT
            self.reward_transition_timer = 0

        elif self.final_winner == WINNER_FOX:
            self.reward_options = FOX_REWARDS
            self.phase = PHASE_REWARD_SELECT
            self.reward_transition_timer = 0

            if self.game_mode == SINGLE_PLAYER:
                self.ai_reward_preview_timer = 0

        else:
            self.reward_options = []
            self.selected_reward = None
            self.phase = PHASE_COMPLETE
            self.complete_transition_timer = 0
            self.complete_hold_timer = 0
            self.mini_game_finished = False

    def choose_ai_fox_reward(self):
        """
        Chooses a fox reward using the main maze situation.

        The fox prioritizes blocking escape, finishing the Grove Shift meter, or
        gaining movement pressure depending on what the player is doing.
        """
        grove_shift = getattr(self, "grove_shift_meter", 0)
        portal_active = getattr(self, "portal_active", False)
        shards_collected = getattr(self, "shards_collected", 0)
        fox_urgency = getattr(self, "fox_urgency", 0)

        # If the player can escape soon, delay the portal.
        if portal_active:
            return REWARD_PORTAL_FLICKER

        if shards_collected >= 2 and fox_urgency >= 55:
            return REWARD_PORTAL_FLICKER

        # If the meter is already high, push toward a fox win.
        if grove_shift >= 70:
            return REWARD_MISCHIEF_SURGE

        if fox_urgency >= 85:
            return REWARD_MISCHIEF_SURGE

        # Otherwise, movement pressure is the best general fox advantage.
        return REWARD_SHADOW_RUSH

    def draw_reward_select(self, screen):
        """Draws the full-screen reward selection image when available."""
        transition_progress = min(
            self.reward_transition_timer / max(self.REWARD_TRANSITION_FRAMES, 1),
            1.0,
        )

        image = self.reward_select_images.get(self.final_winner)

        if image:
            self.draw_gameplay_background(screen)

            screen_image = image.copy()
            screen_image.set_alpha(int(255 * transition_progress))
            screen.blit(screen_image, (0, 0))
            return

        # Fallback if a fullscreen reward image is unavailable.
        self.draw_gameplay_background(screen)

        if self.final_winner == WINNER_HUMAN:
            header = "THE EXPLORER WINS"
        elif self.final_winner == WINNER_FOX:
            header = "THE FOX WINS"
        else:
            header = "THE ECHO IS TIED"

        self.draw_text(
            screen,
            header,
            self.result_font,
            GameTheme.TEXT,
            (512, 120),
            center=True,
        )

        self.draw_text(
            screen,
            "Choose a reward",
            self.reward_font,
            GameTheme.TEXT_SOFT,
            (512, 175),
            center=True,
        )

        self.draw_text(
            screen,
            "Press 1, 2, or 3 to choose",
            self.reward_font,
            GameTheme.TEXT_SOFT,
            (512, 220),
            center=True,
        )

    def draw_reward_to_claimed_transition(self, screen):
        """Crossfades from reward selection screen to reward chosen screen."""
        progress = min(
            self.reward_to_claimed_timer / max(self.REWARD_TO_CLAIMED_FRAMES, 1),
            1.0,
        )

        select_image = self.reward_select_images.get(self.final_winner)
        chosen_image = self.reward_chosen_images.get(self.selected_reward)

        if select_image or chosen_image:
            if select_image:
                select_surface = select_image.copy()
                select_surface.set_alpha(int(255 * (1.0 - progress)))
                screen.blit(select_surface, (0, 0))

            if chosen_image:
                chosen_surface = chosen_image.copy()
                chosen_surface.set_alpha(int(255 * progress))
                screen.blit(chosen_surface, (0, 0))

            return

        # Fallback if images are missing.
        self.draw_gameplay_background(screen)

    def draw_reward_claimed_to_complete_transition(self, screen):
        """
        Holds the chosen reward screen, then fades into the final complete screen.
        """
        fade_start = max(
            0,
            self.REWARD_CLAIMED_HOLD_FRAMES - self.CLAIMED_TO_COMPLETE_FADE_FRAMES,
        )

        if self.reward_claimed_timer < fade_start:
            self.draw_reward_claimed(screen)
            return

        fade_progress = (
            self.reward_claimed_timer - fade_start
        ) / max(self.CLAIMED_TO_COMPLETE_FADE_FRAMES, 1)

        fade_progress = max(0.0, min(1.0, fade_progress))
        fade_progress = self.ease_out_cubic(fade_progress)

        chosen_alpha = int(255 * (1.0 - fade_progress))
        complete_alpha = int(255 * fade_progress)

        image = self.reward_chosen_images.get(self.selected_reward)

        if image:
            chosen_surface = image.copy()
            chosen_surface.set_alpha(chosen_alpha)
            screen.blit(chosen_surface, (0, 0))
        else:
            self.draw_gameplay_background(screen)

        self.draw_echo_complete_screen(screen, alpha=complete_alpha)

    def draw_reward_claimed(self, screen):
        """Draws the chosen reward screen using a full-screen image when available."""
        image = self.reward_chosen_images.get(self.selected_reward)

        if image:
            screen.blit(image, (0, 0))
            return

        # Fallback if a fullscreen reward image is unavailable.
        self.draw_gameplay_background(screen)

        reward_title = "Reward Chosen"

        for reward in HUMAN_REWARDS + FOX_REWARDS:
            if reward["id"] == self.selected_reward:
                reward_title = reward["title"]
                break

        self.draw_text(
            screen,
            reward_title.upper(),
            self.complete_font,
            GameTheme.TEXT,
            (512, 350),
            center=True,
        )

        self.draw_text(
            screen,
            "REWARD CHOSEN",
            self.reward_font,
            GameTheme.TEXT_SOFT,
            (512, 420),
            center=True,
        )

# -----------------------------
# Standalone demo mode
# -----------------------------

def run_standalone_demo():
    """Runs The Sigil's Echo independently for quick demos."""
    pygame.init()

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("The Sigil's Echo")
    clock = pygame.time.Clock()

    # Use SINGLE_PLAYER by default so the fox can progress automatically.
    sigils_echo = SigilsEcho(game_mode=SINGLE_PLAYER)
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
                continue

            sigils_echo.handle_event(event)

        sigils_echo.update()

        if sigils_echo.is_complete():
            running = False
            continue

        sigils_echo.draw(screen)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    run_standalone_demo()
