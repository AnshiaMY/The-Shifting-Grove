"""
settings.py

Shared configuration for The Shifting Grove.

This module defines the constants used by the main maze game and shared systems,
including asset directories, screen dimensions, game state names, player and fox
tuning, maze and portal settings, Grove Shift values, reward effect timings, and
UI transition settings.

Mini-game-specific configuration is intentionally kept inside each mini-game
module:

- sigils_echo.py
- starlight_crossing.py
- cascading_canopy.py

This separation keeps the project easier to maintain: settings.py describes the
main game and shared systems, while each mini-game file owns its own internal
timing, assets, phases, and gameplay rules.
"""

from pathlib import Path


# =============================================================================
# Project paths
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent
ASSET_DIR = BASE_DIR / "assets"
IMAGE_DIR = ASSET_DIR / "images"
FONT_DIR = ASSET_DIR / "fonts"

# =============================================================================
# Main game image assets
# =============================================================================

BACKGROUND_IMAGE = IMAGE_DIR / "background.png"
TITLE_SCREEN_BACKGROUND = IMAGE_DIR / "title_screen_background.png"

PLAYER_IMAGE = IMAGE_DIR / "player.png"
FOX_IMAGE = IMAGE_DIR / "fox.png"

WALL_IMAGE = IMAGE_DIR / "wall.png"
DOOR_IMAGE = IMAGE_DIR / "door.png"
DOOR_LOCKED_IMAGE = IMAGE_DIR / "door_locked.png"

GROVE_SHARD_IMAGE = IMAGE_DIR / "grove_shard.png"
VINES_OVERLAY_IMAGE = IMAGE_DIR / "vines.png"


# =============================================================================
# Menu and instruction assets
# =============================================================================

START_BUTTON_IMAGE = IMAGE_DIR / "start_button.png"
START_BUTTON_HOVER_IMAGE = IMAGE_DIR / "start_button_hover.png"

HOW_TO_PLAY_BUTTON_IMAGE = IMAGE_DIR / "how_to_play_button.png"
HOW_TO_PLAY_BUTTON_HOVER_IMAGE = IMAGE_DIR / "how_to_play_button_hover.png"
HOW_TO_PLAY_SCROLL_IMAGE = IMAGE_DIR / "how_to_play_scroll.png"

QUIT_BUTTON_IMAGE = IMAGE_DIR / "quit_button.png"
QUIT_BUTTON_HOVER_IMAGE = IMAGE_DIR / "quit_button_hover.png"

SINGLE_PLAYER_BUTTON_IMAGE = IMAGE_DIR / "single_player_button.png"
SINGLE_PLAYER_BUTTON_HOVER_IMAGE = IMAGE_DIR / "single_player_button_hover.png"

MULTIPLAYER_BUTTON_IMAGE = IMAGE_DIR / "multiplayer_button.png"
MULTIPLAYER_BUTTON_HOVER_IMAGE = IMAGE_DIR / "multiplayer_button_hover.png"


# =============================================================================
# HUD assets
# =============================================================================

HEART_FULL_IMAGE = IMAGE_DIR / "heart_full.png"
HEART_EMPTY_IMAGE = IMAGE_DIR / "heart_empty.png"


# =============================================================================
# Main maze mini-game trigger assets
# =============================================================================

# These are kept here because game.py draws mini-game triggers inside the maze.
# The mini-games themselves should manage their own internal images.
ECHO_SIGIL_IMAGE = IMAGE_DIR / "echo_sigil.png"
STARLIGHT_CIRCUIT_TRIGGER_IMAGE = IMAGE_DIR / "starlight_circuit_trigger.png"
CANOPY_CASCADE_TRIGGER_IMAGE = IMAGE_DIR / "cascading_canopy_trigger.png"


# =============================================================================
# Font
# =============================================================================

# Optional custom font. If unavailable, the game falls back to a system font.
FANTASY_FONT = FONT_DIR / "fantasy_font.ttf"

# =============================================================================
# Screen and grid settings
# =============================================================================

SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
FPS = 60

TILE_SIZE = 32


# =============================================================================
# Game state names
# =============================================================================

START = "start"
STORY = "story"
MODE_SELECT = "mode_select"
TRANSITION = "transition"
PLAYING = "playing"

HUMAN_WIN = "human_win"

CLAIMED_TRANSITION = "claimed_transition"
ESCAPE_TRANSITION = "escape_transition"
LOSE = "lose"

SIGILS_ECHO = "sigils_echo"
STARLIGHT_CROSSING = "starlight_crossing"
CANOPY_CASCADE = "canopy_cascade"

# =============================================================================
# Game mode names
# =============================================================================

SINGLE_PLAYER = "single_player"
LOCAL_MULTIPLAYER = "local_multiplayer"


def get_mode_display_name(game_mode):
    """Returns a readable label for the selected game mode."""
    if game_mode == SINGLE_PLAYER:
        return "Single Player"

    if game_mode == LOCAL_MULTIPLAYER:
        return "Local Multiplayer"

    return "Unknown Mode"

# =============================================================================
# Fallback colors
# =============================================================================

# Used when an image asset fails to load or when simple fallback drawing is needed.
BACKGROUND_COLOR = (25, 25, 35)
PLAYER_COLOR = (255, 180, 210)
WALL_COLOR = (90, 90, 120)
DOOR_COLOR = (120, 220, 160)
TEXT_COLOR = (255, 255, 255)


# =============================================================================
# Player settings
# =============================================================================

PLAYER_COLLISION_SIZE = 22
PLAYER_SPRITE_SIZE = 64
PLAYER_SPEED = 4

PLAYER_START_X = TILE_SIZE + (TILE_SIZE - PLAYER_COLLISION_SIZE) // 2
PLAYER_START_Y = TILE_SIZE + (TILE_SIZE - PLAYER_COLLISION_SIZE) // 2

PLAYER_MAX_LIVES = 3
PLAYER_START_GLOW_FRAMES = 240


# =============================================================================
# Fox settings
# =============================================================================

FOX_COLLISION_SIZE = 24
FOX_SPRITE_SIZE = 64

FOX_SPEED = 4
FOX_AI_SPEED = 3

FOX_CATCH_COOLDOWN_FRAMES = 120
FOX_RECOVER_FRAMES = 45

FOX_DETECTION_RADIUS_TILES = 7
FOX_MEMORY_FRAMES = 180
FOX_PREDICT_TILES = 3

FOX_PATH_RECALCULATE_FRAMES = 15
FOX_PATROL_RECALCULATE_FRAMES = 90


# =============================================================================
# Maze, portal, and shard settings
# =============================================================================

DOOR_SPRITE_SIZE = 96

SHARD_COUNT = 3
SHARD_SPRITE_SIZE = 44
SHARD_COLLISION_SIZE = 24

PORTAL_GUARD_RADIUS = 92
PORTAL_REPEL_STRENGTH = 7


# =============================================================================
# Grove Shift / Mischief meter settings
# =============================================================================

GROVE_SHIFT_MAX = 100
GROVE_SHIFT_CATCH_GAIN = 18

GROVE_SHIFT_NEAR_RADIUS_TILES = 4
GROVE_SHIFT_NEAR_GAIN = 0.012

GROVE_SHIFT_PORTAL_ACTIVE_MULTIPLIER = 1.25


# =============================================================================
# Shared reward effect settings
# =============================================================================

# These are shared because all mini-games can return the same reward IDs.
REWARD_METER_AMOUNT = 15

REWARD_FOX_BANISH_FRAMES = FPS * 5
REWARD_SHADOW_RUSH_FRAMES = FPS * 5
REWARD_PORTAL_FLICKER_FRAMES = FPS * 5
REWARD_SHADOW_RUSH_MULTIPLIER = 1.35


# =============================================================================
# Main maze mini-game trigger settings
# =============================================================================

ECHO_SIGIL_SIZE = 38
STARLIGHT_CROSSING_TRIGGER_SIZE = 38
CANOPY_CASCADE_TRIGGER_SIZE = 38


# =============================================================================
# UI and readability settings
# =============================================================================

GAMEPLAY_BACKGROUND_SOFTEN_ALPHA = 22
TOAST_DURATION_FRAMES = 120


# =============================================================================
# Transition and visual effect settings
# =============================================================================

TRANSITION_FADE_SPEED = 4
TRANSITION_HOLD_FRAMES = 120

CLAIMED_TRANSITION_FRAMES = 150
ESCAPE_TRANSITION_FRAMES = 150

MIST_PARTICLE_COUNT = 70
MIST_MAX_ALPHA = 255

MIST_VEIL_COLOR = (190, 225, 245)
MIST_PARTICLE_COLOR = (240, 248, 255)
