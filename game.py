"""
game.py

Main coordinator for The Shifting Grove.

This module controls the high-level game loop, state transitions, menu flow,
main maze gameplay, player and fox updates, shard collection, portal activation,
Grove Shift Meter behavior, win/loss conditions, and mini-game integration.

The main maze owns the shared systems that affect the full game experience:
- player lives
- Grove Shift Meter
- fox catch logic
- portal guard behavior
- temporary reward effects
- mini-game trigger spawning
- transition screens

Each mini-game owns its own internal rules, timing, drawing, and reward
selection flow. game.py is responsible for starting the selected mini-game,
pausing the maze while it runs, receiving the returned reward, and applying that
reward to the main game state.
"""

import math
import random
from pathlib import Path

import pygame

from asset_loader import load_image
from fox import Fox
from maze import Maze
from player import Player
from shard import GroveShard
from sigils_echo import (
    REWARD_FOX_BANISH,
    REWARD_GROVE_CALM,
    REWARD_LANTERN_SHIELD,
    REWARD_MISCHIEF_SURGE,
    REWARD_PORTAL_FLICKER,
    REWARD_SHADOW_RUSH,
    SigilsEcho,
)

from starlight_crossing import (
    DIFFICULTY_MEDIUM_HARD,
    StarlightCrossing,
)

from cascading_canopy import CanopyCascade

from ui import GameUI, ImageButton
from settings import (
    BACKGROUND_COLOR,
    BACKGROUND_IMAGE,
    CLAIMED_TRANSITION,
    CLAIMED_TRANSITION_FRAMES,
    ECHO_SIGIL_IMAGE,
    ECHO_SIGIL_SIZE,
    ESCAPE_TRANSITION,
    ESCAPE_TRANSITION_FRAMES,
    FANTASY_FONT,
    FOX_AI_SPEED,
    FOX_CATCH_COOLDOWN_FRAMES,
    FOX_COLLISION_SIZE,
    FOX_SPEED,
    FPS,
    GAMEPLAY_BACKGROUND_SOFTEN_ALPHA,
    GROVE_SHIFT_CATCH_GAIN,
    GROVE_SHIFT_MAX,
    GROVE_SHIFT_NEAR_GAIN,
    GROVE_SHIFT_NEAR_RADIUS_TILES,
    GROVE_SHIFT_PORTAL_ACTIVE_MULTIPLIER,
    GROVE_SHARD_IMAGE,
    HEART_EMPTY_IMAGE,
    HEART_FULL_IMAGE,
    HUMAN_WIN,
    HOW_TO_PLAY_BUTTON_HOVER_IMAGE,
    HOW_TO_PLAY_BUTTON_IMAGE,
    LOSE,
    MIST_MAX_ALPHA,
    MIST_PARTICLE_COUNT,
    MODE_SELECT,
    MULTIPLAYER_BUTTON_HOVER_IMAGE,
    MULTIPLAYER_BUTTON_IMAGE,
    PLAYER_MAX_LIVES,
    PLAYER_START_X,
    PLAYER_START_Y,
    PLAYING,
    PORTAL_GUARD_RADIUS,
    PORTAL_REPEL_STRENGTH,
    QUIT_BUTTON_HOVER_IMAGE,
    QUIT_BUTTON_IMAGE,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SHARD_COUNT,
    LOCAL_MULTIPLAYER,
    SINGLE_PLAYER,
    SIGILS_ECHO,
    CANOPY_CASCADE,
    CANOPY_CASCADE_TRIGGER_IMAGE,
    REWARD_FOX_BANISH_FRAMES,
    REWARD_METER_AMOUNT,
    REWARD_PORTAL_FLICKER_FRAMES,
    REWARD_SHADOW_RUSH_FRAMES,
    REWARD_SHADOW_RUSH_MULTIPLIER,
    STARLIGHT_CIRCUIT_TRIGGER_IMAGE,
    STARLIGHT_CROSSING,
    SINGLE_PLAYER_BUTTON_HOVER_IMAGE,
    SINGLE_PLAYER_BUTTON_IMAGE,
    START,
    START_BUTTON_HOVER_IMAGE,
    START_BUTTON_IMAGE,
    STORY,
    TEXT_COLOR,
    TILE_SIZE,
    TITLE_SCREEN_BACKGROUND,
    TRANSITION,
    TRANSITION_FADE_SPEED,
    TRANSITION_HOLD_FRAMES,
    VINES_OVERLAY_IMAGE,
)


class Game:
    """Main controller for The Shifting Grove."""

    MENU_BUTTON_SIZE = (420, 115)
    MENU_BUTTON_X = 65
    MENU_BUTTON_GAP = 125

    def __init__(self):
        pygame.init()

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("The Shifting Grove")

        self.clock = pygame.time.Clock()
        self.running = True
        self.state = START
        self.game_mode = SINGLE_PLAYER

        # Start-game mist transition.
        self.transition_alpha = 0
        self.transition_direction = "fade_in"
        self.transition_target_state = PLAYING
        self.transition_has_reset_level = False
        self.transition_hold_timer = 0

        # Lose cinematic transition.
        self.claimed_timer = 0
        self.claimed_reason = "grove"

        # Win cinematic transition.
        self.escape_timer = 0
        self.escape_portal_center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)

        # Core gameplay state.
        self.shards_collected = 0
        self.portal_is_active = False
        self.player_lives = PLAYER_MAX_LIVES
        self.grove_shift_meter = 0
        self.fox_catch_cooldown = 0

        # Mini-game state.
        self.sigils_echo = None
        self.starlight_crossing = None
        self.canopy_cascade = None

        self.mini_game_trigger_rect = None
        self.mini_game_trigger_available = True
        self.mini_game_trigger_spawned = False
        self.mini_game_trigger_spawn_timer = 0

        self.active_mini_game_type = SIGILS_ECHO
        self.last_mini_game_type = None
        self.same_mini_game_streak = 0

        # Reward effect state.
        self.lantern_shield_active = False
        self.fox_banish_timer = 0
        self.shadow_rush_timer = 0
        self.portal_flicker_timer = 0
        self.pending_portal_flicker = False

        self.background_image = load_image(
            BACKGROUND_IMAGE,
            (SCREEN_WIDTH, SCREEN_HEIGHT),
            use_alpha=True,
        )

        self.title_screen_background = load_image(
            TITLE_SCREEN_BACKGROUND,
            (SCREEN_WIDTH, SCREEN_HEIGHT),
            use_alpha=True,
        )

        raw_how_to_play_fullscreen = load_image(
            Path("assets/images/how_to_play_fullscreen.png"),
            use_alpha=False,
        )

        self.how_to_play_fullscreen = None
        if raw_how_to_play_fullscreen:
            self.how_to_play_fullscreen = pygame.transform.smoothscale(
                raw_how_to_play_fullscreen,
                (SCREEN_WIDTH, SCREEN_HEIGHT),
            )

        self.vines_overlay_image = load_image(
            VINES_OVERLAY_IMAGE,
            (SCREEN_WIDTH, SCREEN_HEIGHT),
            use_alpha=True,
        )


        raw_echo_sigil_image = load_image(ECHO_SIGIL_IMAGE, use_alpha=True)
        self.echo_sigil_image = self.scale_image_to_height(raw_echo_sigil_image, 58)

        raw_starlight_trigger_image = load_image(
            STARLIGHT_CIRCUIT_TRIGGER_IMAGE,
            use_alpha=True,
        )
        self.starlight_trigger_image = self.scale_image_to_height(raw_starlight_trigger_image, 58)

        raw_canopy_trigger_image = load_image(CANOPY_CASCADE_TRIGGER_IMAGE, use_alpha=True)
        self.canopy_trigger_image = self.scale_image_to_height(raw_canopy_trigger_image, 58)

        self.large_font = self.load_font(72)
        self.medium_font = self.load_font(42)
        self.small_font = self.load_font(30)
        self.tiny_font = self.load_font(22)

        raw_shard_icon = load_image(GROVE_SHARD_IMAGE, use_alpha=True)
        self.shard_icon = self.scale_image_to_height(raw_shard_icon, 24)

        raw_heart_full_icon = load_image(HEART_FULL_IMAGE, use_alpha=True)
        self.heart_full_icon = self.scale_image_to_height(raw_heart_full_icon, 30)

        raw_heart_empty_icon = load_image(HEART_EMPTY_IMAGE, use_alpha=True)
        self.heart_empty_icon = self.scale_image_to_height(raw_heart_empty_icon, 30)

        self.ui = GameUI(
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
            mist_particle_count=MIST_PARTICLE_COUNT,
            shard_icon=self.shard_icon,
            heart_full_icon=self.heart_full_icon,
            heart_empty_icon=self.heart_empty_icon,
            large_font=self.large_font,
            medium_font=self.medium_font,
            small_font=self.small_font,
            tiny_font=self.tiny_font,
        )

        self.create_menu_buttons()
        self.reset_level()

    # -----------------------------
    # Loading helpers
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

    def load_font(self, size):
        """Loads the custom fantasy font if available."""
        if FANTASY_FONT.exists():
            return pygame.font.Font(str(FANTASY_FONT), size)

        return pygame.font.Font(None, size)

    # -----------------------------
    # Setup methods
    # -----------------------------

    def get_button_image_path(self, preferred_path, fallback_path):
        """Returns the preferred button image path if it exists."""
        if preferred_path.exists():
            return preferred_path

        return fallback_path

    def create_menu_buttons(self):
        """Creates the title and mode selection image buttons."""
        title_start_y = 270

        self.start_button = ImageButton(
            self.MENU_BUTTON_X,
            title_start_y,
            START_BUTTON_IMAGE,
            START_BUTTON_HOVER_IMAGE,
            size=self.MENU_BUTTON_SIZE,
        )

        self.how_to_play_button = ImageButton(
            self.MENU_BUTTON_X,
            title_start_y + self.MENU_BUTTON_GAP,
            HOW_TO_PLAY_BUTTON_IMAGE,
            HOW_TO_PLAY_BUTTON_HOVER_IMAGE,
            size=self.MENU_BUTTON_SIZE,
        )

        self.quit_button = ImageButton(
            self.MENU_BUTTON_X,
            title_start_y + (self.MENU_BUTTON_GAP * 2),
            QUIT_BUTTON_IMAGE,
            QUIT_BUTTON_HOVER_IMAGE,
            size=self.MENU_BUTTON_SIZE,
        )

        mode_start_y = 315

        single_player_image = self.get_button_image_path(
            SINGLE_PLAYER_BUTTON_IMAGE,
            START_BUTTON_IMAGE,
        )
        single_player_hover_image = self.get_button_image_path(
            SINGLE_PLAYER_BUTTON_HOVER_IMAGE,
            START_BUTTON_HOVER_IMAGE,
        )

        multiplayer_image = self.get_button_image_path(
            MULTIPLAYER_BUTTON_IMAGE,
            START_BUTTON_IMAGE,
        )
        multiplayer_hover_image = self.get_button_image_path(
            MULTIPLAYER_BUTTON_HOVER_IMAGE,
            START_BUTTON_HOVER_IMAGE,
        )

        self.single_player_button = ImageButton(
            self.MENU_BUTTON_X,
            mode_start_y,
            single_player_image,
            single_player_hover_image,
            size=self.MENU_BUTTON_SIZE,
        )

        self.multiplayer_button = ImageButton(
            self.MENU_BUTTON_X,
            mode_start_y + self.MENU_BUTTON_GAP,
            multiplayer_image,
            multiplayer_hover_image,
            size=self.MENU_BUTTON_SIZE,
        )

    def reset_level(self):
        """Creates a fresh maze and resets all gameplay state."""
        self.maze = Maze()
        self.wall_rects = self.maze.get_wall_rects()

        self.player = Player(PLAYER_START_X, PLAYER_START_Y)
        self.fox = self.create_fox()

        self.shards_collected = 0
        self.portal_is_active = False
        self.player_lives = PLAYER_MAX_LIVES
        self.grove_shift_meter = 0
        self.fox_catch_cooldown = 0

        self.claimed_timer = 0
        self.claimed_reason = "grove"

        self.escape_timer = 0
        self.escape_portal_center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)

        self.sigils_echo = None
        self.starlight_crossing = None
        self.canopy_cascade = None

        # Randomly choose which mini-game trigger appears first this level.
        self.schedule_next_mini_game_trigger(min_seconds=5, max_seconds=10)

        self.lantern_shield_active = False
        self.fox_banish_timer = 0
        self.shadow_rush_timer = 0
        self.portal_flicker_timer = 0
        self.pending_portal_flicker = False

        self.shards = self.create_grove_shards()
        self.mini_game_trigger_rect = None

        self.ui.reset_level_feedback()

    def create_grove_shards(self):
        """Creates Grove Shards on random valid open maze tiles."""
        possible_tiles = self.get_valid_shard_tiles()

        if len(possible_tiles) < SHARD_COUNT:
            selected_tiles = possible_tiles
        else:
            selected_tiles = random.sample(possible_tiles, SHARD_COUNT)

        shards = []

        for col, row in selected_tiles:
            center_x = col * TILE_SIZE + TILE_SIZE // 2
            center_y = row * TILE_SIZE + TILE_SIZE // 2
            shards.append(GroveShard(center_x, center_y))

        return shards

    def create_fox(self):
        """Creates the fox on a valid open tile far from the player."""
        valid_tiles = self.get_valid_fox_tiles()

        if valid_tiles:
            col, row = random.choice(valid_tiles)
        else:
            col = self.maze.cols - 2
            row = self.maze.rows - 2

        fox_x = col * TILE_SIZE + (TILE_SIZE - FOX_COLLISION_SIZE) // 2
        fox_y = row * TILE_SIZE + (TILE_SIZE - FOX_COLLISION_SIZE) // 2

        return Fox(fox_x, fox_y)

    def create_mini_game_trigger_rect(self):
        """Creates one shared mini-game trigger on a valid open maze tile."""
        possible_tiles = self.get_valid_shard_tiles()

        if not possible_tiles:
            return None

        blocked_tiles = set()

        if hasattr(self, "shards"):
            for shard in self.shards:
                blocked_tiles.add(
                    (
                        shard.rect.centerx // TILE_SIZE,
                        shard.rect.centery // TILE_SIZE,
                    )
                )

        safe_tiles = []

        for col, row in possible_tiles:
            if (col, row) in blocked_tiles:
                continue

            center_x = col * TILE_SIZE + TILE_SIZE // 2
            center_y = row * TILE_SIZE + TILE_SIZE // 2

            if self.is_point_too_close_to_actor(center_x, center_y, self.player, 4):
                continue

            if self.is_point_too_close_to_actor(center_x, center_y, self.fox, 4):
                continue

            safe_tiles.append((col, row))

        if safe_tiles:
            chosen_tile = random.choice(safe_tiles)
        else:
            chosen_tile = random.choice(possible_tiles)

        col, row = chosen_tile

        center_x = col * TILE_SIZE + TILE_SIZE // 2
        center_y = row * TILE_SIZE + TILE_SIZE // 2

        return pygame.Rect(
            center_x - ECHO_SIGIL_SIZE // 2,
            center_y - ECHO_SIGIL_SIZE // 2,
            ECHO_SIGIL_SIZE,
            ECHO_SIGIL_SIZE,
        )

    def is_point_too_close_to_actor(self, x, y, actor, min_distance_tiles):
        """Returns True if a spawn point is too close to the player or fox."""
        if actor is None or not hasattr(actor, "rect"):
            return False

        actor_x, actor_y = actor.rect.center
        distance = math.hypot(x - actor_x, y - actor_y)
        return distance < TILE_SIZE * min_distance_tiles

    def get_valid_shard_tiles(self):
        """Finds open maze tiles where shards and mini-game triggers can spawn."""
        valid_tiles = []
        door_center = None

        if self.maze.door_rect:
            door_center = self.maze.door_rect.center

        for row_index, row in enumerate(self.maze.layout):
            for col_index, tile in enumerate(row):
                if tile != "0":
                    continue

                tile_center_x = col_index * TILE_SIZE + TILE_SIZE // 2
                tile_center_y = row_index * TILE_SIZE + TILE_SIZE // 2

                distance_from_start = abs(tile_center_x - PLAYER_START_X) + abs(
                    tile_center_y - PLAYER_START_Y
                )

                if distance_from_start < TILE_SIZE * 7:
                    continue

                if door_center:
                    distance_from_door = abs(tile_center_x - door_center[0]) + abs(
                        tile_center_y - door_center[1]
                    )

                    if distance_from_door < TILE_SIZE * 5:
                        continue

                valid_tiles.append((col_index, row_index))

        return valid_tiles

    def get_valid_fox_tiles(self):
        """Finds open maze tiles where the fox is allowed to spawn."""
        valid_tiles = []

        if hasattr(self, "player"):
            avoid_x, avoid_y = self.player.rect.center
        else:
            avoid_x = PLAYER_START_X
            avoid_y = PLAYER_START_Y

        for row_index, row in enumerate(self.maze.layout):
            for col_index, tile in enumerate(row):
                if tile != "0":
                    continue

                tile_center_x = col_index * TILE_SIZE + TILE_SIZE // 2
                tile_center_y = row_index * TILE_SIZE + TILE_SIZE // 2

                distance_from_player = abs(tile_center_x - avoid_x) + abs(
                    tile_center_y - avoid_y
                )

                if distance_from_player < TILE_SIZE * 14:
                    continue

                valid_tiles.append((col_index, row_index))

        return valid_tiles

    # -----------------------------
    # State transitions
    # -----------------------------

    def start_transition(self, target_state=PLAYING, reset_level=True):
        """Starts the mist-based transition."""
        self.state = TRANSITION
        self.transition_alpha = 0
        self.transition_direction = "fade_in"
        self.transition_target_state = target_state
        self.transition_has_reset_level = not reset_level
        self.transition_hold_timer = 0

    def start_game_mode(self, selected_mode):
        """
        Stores the selected mode and starts the game transition.

        The level is reset before the transition begins so the player never sees an
        old maze flicker underneath the Grove shifting screen.
        """
        self.game_mode = selected_mode

        # Create the new maze immediately before the transition begins.
        self.reset_level()

        # Start the transition, but do not reset again during the hold phase.
        self.start_transition(target_state=PLAYING, reset_level=False)

        # Start from transparent mist so the Grove shifting effect fades in smoothly.
        self.transition_alpha = 0
        self.transition_direction = "fade_in"
        self.transition_hold_timer = 0

    def start_claimed_transition(self, reason="grove"):
        """Starts the cinematic claimed transition."""
        if self.state != PLAYING:
            return

        self.claimed_reason = reason
        self.claimed_timer = 0
        self.state = CLAIMED_TRANSITION

    def start_escape_transition(self):
        """Starts the human escape cinematic transition."""
        if self.state != PLAYING:
            return

        if self.maze.door_rect:
            self.escape_portal_center = self.maze.door_rect.center
        else:
            self.escape_portal_center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)

        self.escape_timer = 0
        self.state = ESCAPE_TRANSITION

    def start_sigils_echo(self, started_by="human"):
        """
        Starts The Sigil's Echo.

        Normal maze gameplay pauses immediately. The SigilsEcho object owns its
        own intro transition, instructions, challenge rounds, and reward screen.
        """
        if self.state != PLAYING:
            return

        self.mini_game_trigger_available = False

        self.sigils_echo = SigilsEcho(
            game_mode=self.game_mode,
            large_font=self.large_font,
            medium_font=self.medium_font,
            small_font=self.small_font,
            tiny_font=self.tiny_font,
        )

        toast_message = (
            "The fox awakens the Echo Sigil..."
            if started_by == "fox"
            else "The Echo Sigil awakens..."
        )
        self.ui.show_toast(toast_message, duration=85)
        self.state = SIGILS_ECHO

    def start_starlight_crossing(self, started_by="human"):
        """
        Starts Starlight Crossing.

        Normal maze gameplay pauses immediately. StarlightCrossing owns its own intro,
        instructions, gameplay, reward selection, and completion screen.
        """
        if self.state != PLAYING:
            return

        self.mini_game_trigger_available = False

        self.starlight_crossing = StarlightCrossing(
            game_mode=self.game_mode,
            difficulty=DIFFICULTY_MEDIUM_HARD,
            standalone_debug=False,
        )

        toast_message = (
            "The fox awakens Starlight Crossing..."
            if started_by == "fox"
            else "Starlight Crossing awakens..."
        )
        self.ui.show_toast(toast_message, duration=85)
        self.state = STARLIGHT_CROSSING

    def start_canopy_cascade(self, started_by="human"):
        """
        Starts Canopy Cascade.

        Normal maze gameplay pauses immediately. CanopyCascade owns its own intro,
        instructions, gameplay, reward selection, and completion screen.
        """
        if self.state != PLAYING:
            return

        self.mini_game_trigger_available = False

        self.canopy_cascade = CanopyCascade(game_mode=self.game_mode)

        toast_message = (
            "The fox awakens Canopy Cascade..."
            if started_by == "fox"
            else "Canopy Cascade awakens..."
        )
        self.ui.show_toast(toast_message, duration=85)
        self.state = CANOPY_CASCADE

    # -----------------------------
    # Main loop
    # -----------------------------

    def run(self):
        """Runs the game loop until the window is closed."""
        while self.running:
            self.handle_events()
            self.update()
            self.draw()

        pygame.quit()

    # -----------------------------
    # Event handling
    # -----------------------------

    def handle_events(self):
        """Routes events based on the current game state."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if self.state == START:
                self.handle_start_screen_events(event)

            elif self.state == STORY:
                self.handle_story_screen_events(event)

            elif self.state == MODE_SELECT:
                self.handle_mode_select_events(event)

            elif self.state == PLAYING:
                self.handle_playing_events(event)

            elif self.state == SIGILS_ECHO:
                self.handle_sigils_echo_events(event)

            elif self.state == STARLIGHT_CROSSING:
                self.handle_starlight_crossing_events(event)

            elif self.state == CANOPY_CASCADE:
                self.handle_canopy_cascade_events(event)

            elif self.state == HUMAN_WIN:
                self.handle_win_screen_events(event)


            elif self.state == LOSE:
                self.handle_lose_screen_events(event)

    def handle_start_screen_events(self, event):
        """Handles title screen clicks."""
        if self.start_button.is_clicked(event):
            self.state = MODE_SELECT

        elif self.how_to_play_button.is_clicked(event):
            self.state = STORY

        elif self.quit_button.is_clicked(event):
            self.running = False

    def handle_story_screen_events(self, event):
        """Handles How to Play screen keyboard input."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self.state = MODE_SELECT

            elif event.key == pygame.K_ESCAPE:
                self.state = START

    def handle_mode_select_events(self, event):
        """Handles Single Player / Local Multiplayer selection."""
        if self.single_player_button.is_clicked(event):
            self.start_game_mode(SINGLE_PLAYER)

        elif self.multiplayer_button.is_clicked(event):
            self.start_game_mode(LOCAL_MULTIPLAYER)

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.state = START

            elif event.key == pygame.K_1:
                self.start_game_mode(SINGLE_PLAYER)

            elif event.key == pygame.K_2:
                self.start_game_mode(LOCAL_MULTIPLAYER)

    def handle_playing_events(self, event):
        """Handles gameplay input during active play."""
        pass

    def handle_sigils_echo_events(self, event):
        """Passes input into The Sigil's Echo."""
        if self.sigils_echo:
            self.sigils_echo.handle_event(event)

    def handle_starlight_crossing_events(self, event):
        """Passes input into Starlight Crossing."""
        if self.starlight_crossing:
            self.starlight_crossing.handle_event(event)

    def handle_canopy_cascade_events(self, event):
        """Passes input into Canopy Cascade."""
        if self.canopy_cascade:
            self.canopy_cascade.handle_event(event)

    def handle_win_screen_events(self, event):
        """Handles human win screen keyboard input."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                self.state = MODE_SELECT

            elif event.key == pygame.K_ESCAPE:
                self.state = START


    def handle_lose_screen_events(self, event):
        """Handles lose screen keyboard input."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                self.state = MODE_SELECT

            elif event.key == pygame.K_ESCAPE:
                self.state = START

    # -----------------------------
    # Update methods
    # -----------------------------

    def update(self):
        """Updates the current game state."""
        if self.state == START:
            self.start_button.update()
            self.how_to_play_button.update()
            self.quit_button.update()

        elif self.state == MODE_SELECT:
            self.single_player_button.update()
            self.multiplayer_button.update()

        elif self.state == TRANSITION:
            self.update_transition()

        elif self.state == PLAYING:
            self.update_playing_state()

        elif self.state == SIGILS_ECHO:
            self.update_sigils_echo_state()

        elif self.state == STARLIGHT_CROSSING:
            self.update_starlight_crossing_state()

        elif self.state == CANOPY_CASCADE:
            self.update_canopy_cascade_state()

        elif self.state == CLAIMED_TRANSITION:
            self.update_claimed_transition()

        elif self.state == ESCAPE_TRANSITION:
            self.update_escape_transition()

        elif self.state in (HUMAN_WIN, LOSE):
            self.ui.update()

    def update_playing_state(self):
        """Updates active gameplay."""
        self.update_reward_timers()

        self.player.update(self.wall_rects)
        self.update_fox_system()

        if self.state != PLAYING:
            self.ui.update()
            return

        self.update_grove_shift_pressure()

        if self.state != PLAYING:
            self.ui.update()
            return

        self.update_shards()

        if self.state != PLAYING:
            self.ui.update()
            return

        self.update_mini_game_trigger_spawn()
        self.check_mini_game_trigger()

        if self.state != PLAYING:
            self.ui.update()
            return

        self.check_human_win_condition()
        self.ui.update()

    def update_transition(self):
        """Updates the transition state and transition visuals."""
        self.ui.update_transition()

        if self.transition_direction == "fade_in":
            self.transition_alpha += TRANSITION_FADE_SPEED

            if self.transition_alpha >= MIST_MAX_ALPHA:
                self.transition_alpha = MIST_MAX_ALPHA
                self.transition_direction = "hold"

        elif self.transition_direction == "hold":
            self.transition_hold_timer += 1

            if not self.transition_has_reset_level:
                self.reset_level()
                self.transition_has_reset_level = True

            if self.transition_hold_timer >= TRANSITION_HOLD_FRAMES:
                self.transition_direction = "fade_out"

        elif self.transition_direction == "fade_out":
            self.transition_alpha -= TRANSITION_FADE_SPEED

            if self.transition_alpha <= 0:
                self.transition_alpha = 0
                self.state = self.transition_target_state

    def update_sigils_echo_state(self):
        """
        Updates The Sigil's Echo while normal maze gameplay is paused.

        The mini-game owns its own transition, instructions, pattern reveal,
        round results, and reward selection screen. The maze only updates the
        mini-game and applies the selected reward when it finishes.
        """
        self.ui.update()

        if self.sigils_echo is None:
            self.sigils_echo = SigilsEcho(
                game_mode=self.game_mode,
                large_font=self.large_font,
                medium_font=self.medium_font,
                small_font=self.small_font,
                tiny_font=self.tiny_font,
            )

        # Give the mini-game live main-game context.
        # This lets the AI fox choose smarter rewards instead of always defaulting.
        self.sigils_echo.portal_active = self.portal_is_active
        self.sigils_echo.grove_shift_meter = self.grove_shift_meter
        self.sigils_echo.shards_collected = self.shards_collected
        self.sigils_echo.fox_urgency = self.calculate_fox_urgency()

        self.sigils_echo.update(
            portal_is_active=self.portal_is_active,
            grove_shift_meter=self.grove_shift_meter,
        )

        if self.sigils_echo.is_complete():
            selected_reward = self.sigils_echo.get_selected_reward()

            self.sigils_echo = None
            self.state = PLAYING

            if selected_reward:
                self.apply_mini_game_reward(selected_reward)

            # Schedule another random mini-game trigger later.
            self.schedule_next_mini_game_trigger(min_seconds=10, max_seconds=20)

    def update_starlight_crossing_state(self):
        """
        Updates Starlight Crossing while normal maze gameplay is paused.

        The maze only updates the mini-game and applies the selected reward when it
        finishes.
        """
        self.ui.update()

        if self.starlight_crossing is None:
            self.starlight_crossing = StarlightCrossing(
                game_mode=self.game_mode,
                difficulty=DIFFICULTY_MEDIUM_HARD,
                standalone_debug=False,
            )

        # Give the mini-game live main-game context for smarter Fox reward choices.
        self.starlight_crossing.gameplay.portal_active = self.portal_is_active
        self.starlight_crossing.gameplay.grove_shift_meter = self.grove_shift_meter
        self.starlight_crossing.gameplay.shards_collected = self.shards_collected
        self.starlight_crossing.gameplay.fox_urgency = self.calculate_fox_urgency()

        self.starlight_crossing.update()

        if self.starlight_crossing.is_complete():
            selected_reward = self.starlight_crossing.get_selected_reward()

            self.starlight_crossing = None
            self.state = PLAYING

            if selected_reward:
                self.apply_mini_game_reward(selected_reward)

            # Schedule another random mini-game trigger later.
            self.schedule_next_mini_game_trigger(min_seconds=10, max_seconds=20)

    def update_canopy_cascade_state(self):
        """
        Updates Canopy Cascade while normal maze gameplay is paused.

        The maze only updates the mini-game and applies the selected reward when it
        finishes.
        """
        self.ui.update()

        if self.canopy_cascade is None:
            self.canopy_cascade = CanopyCascade(game_mode=self.game_mode)

        self.canopy_cascade.update()

        if self.canopy_cascade.is_complete():
            selected_reward = self.canopy_cascade.get_selected_reward()

            self.canopy_cascade = None
            self.state = PLAYING

            if selected_reward:
                self.apply_mini_game_reward(selected_reward)

            # Schedule another random mini-game trigger later.
            self.schedule_next_mini_game_trigger(min_seconds=10, max_seconds=20)

    def update_claimed_transition(self):
        """Updates the cinematic claimed transition."""
        self.claimed_timer += 1
        self.ui.update()

        if self.claimed_timer >= CLAIMED_TRANSITION_FRAMES:
            self.state = LOSE

    def update_escape_transition(self):
        """Updates the human escape transition."""
        self.escape_timer += 1
        self.ui.update()

        if self.escape_timer >= ESCAPE_TRANSITION_FRAMES:
            self.state = HUMAN_WIN

    def update_reward_timers(self):
        """Updates temporary reward effects during normal gameplay."""
        if self.fox_banish_timer > 0:
            self.fox_banish_timer -= 1

        if self.shadow_rush_timer > 0:
            self.shadow_rush_timer -= 1
            self.fox.speed = FOX_SPEED * REWARD_SHADOW_RUSH_MULTIPLIER
            self.fox.ai_speed = FOX_AI_SPEED * REWARD_SHADOW_RUSH_MULTIPLIER
        else:
            self.fox.speed = FOX_SPEED
            self.fox.ai_speed = FOX_AI_SPEED

        if self.portal_flicker_timer > 0:
            self.portal_flicker_timer -= 1

    def update_shards(self):
        """Updates shard animation and checks collection collisions."""
        for shard in self.shards:
            shard.update()

            if shard.collected:
                continue

            if self.player.rect.colliderect(shard.rect):
                self.collect_shard(shard)

    def calculate_fox_urgency(self):
        """
        Calculates how urgently the fox should act.

        Higher urgency means the player is closer to escaping, so the fox becomes
        more strategic about seeking mini-games and pressuring objectives.
        """
        urgency = 0

        # Shard progress is the main signal that the player is getting close.
        if SHARD_COUNT > 0:
            shard_progress = self.shards_collected / SHARD_COUNT
            urgency += int(shard_progress * 45)

        # Portal active means the player can escape soon.
        if self.portal_is_active:
            urgency += 35

        # If the Grove Shift Meter is low, the fox is behind.
        grove_progress = self.grove_shift_meter / max(GROVE_SHIFT_MAX, 1)

        if grove_progress < 0.30:
            urgency += 15
        elif grove_progress < 0.55:
            urgency += 8

        # If the player still has lives, the fox has more work to do.
        if self.player_lives >= PLAYER_MAX_LIVES:
            urgency += 8

        # If a mini-game trigger exists, seeking it becomes a possible comeback play.
        if self.mini_game_trigger_available and self.mini_game_trigger_rect is not None:
            urgency += 12

        return max(0, min(100, urgency))

    def update_fox_system(self):
        """Updates fox movement, catch logic, and anti-camping behavior."""
        if self.fox_banish_timer > 0:
            return

        if self.game_mode == SINGLE_PLAYER:
            self.fox.update_ai(
                player=self.player,
                maze_layout=self.maze.layout,
                wall_rects=self.wall_rects,
                shards=self.shards,
                portal_is_active=self.portal_is_active,
                portal_rect=self.maze.door_rect,
                shards_collected=self.shards_collected,
                mini_game_trigger_rect=self.mini_game_trigger_rect,
                mini_game_available=self.mini_game_trigger_available,
                fox_urgency=self.calculate_fox_urgency(),
            )

        elif self.game_mode == LOCAL_MULTIPLAYER:
            self.fox.update_multiplayer(self.wall_rects)

        if self.fox_catch_cooldown > 0:
            self.fox_catch_cooldown -= 1
            self.apply_portal_guard_to_fox()
            return

        if self.player.rect.colliderect(self.fox.rect):
            if self.lantern_shield_active:
                self.lantern_shield_active = False
                self.reset_positions_after_fox_catch()
                self.ui.show_toast("Lantern Shield blocked the fox!", duration=110)
                return

            self.add_grove_shift(GROVE_SHIFT_CATCH_GAIN)

            if self.state != PLAYING:
                return

            self.lose_life()

            if self.state != PLAYING:
                return

            self.reset_positions_after_fox_catch()
            self.ui.show_toast("The fox caught you", duration=90)
            return

        self.apply_portal_guard_to_fox()

    def update_grove_shift_pressure(self):
        """
        Fills the Grove Shift Meter from both ambient danger and fox pressure.

        The Grove should feel threatening even when the fox is not actively catching
        the player. Fox proximity, shard progress, and portal activation all make
        the meter rise faster.
        """
        if self.state != PLAYING:
            return

        gain = 0

        # 1. Ambient Grove pressure.
        # This makes the maze itself feel dangerous over time.
        gain += 0.006

        # 2. Shard pressure.
        # The more shards the player collects, the more unstable the Grove becomes.
        gain += self.shards_collected * 0.004

        # 3. Portal pressure.
        # Once the portal is active, the Grove should feel urgent.
        if self.portal_is_active:
            gain += 0.018

        # 4. Fox proximity pressure.
        fox_x, fox_y = self.fox.rect.center
        player_x, player_y = self.player.rect.center

        dx = fox_x - player_x
        dy = fox_y - player_y

        distance = math.hypot(dx, dy)
        pressure_radius = GROVE_SHIFT_NEAR_RADIUS_TILES * TILE_SIZE

        if distance <= pressure_radius:
            closeness = 1 - (distance / max(pressure_radius, 1))

            # Base nearby pressure plus extra danger when the fox is very close.
            nearby_gain = GROVE_SHIFT_NEAR_GAIN * (1.8 + closeness * 3.2)

            if self.portal_is_active:
                nearby_gain *= GROVE_SHIFT_PORTAL_ACTIVE_MULTIPLIER

            gain += nearby_gain

        self.add_grove_shift(gain)

    def add_grove_shift(self, amount):
        """Adds to the Grove Shift Meter and triggers claiming if full."""
        if self.state != PLAYING:
            return

        self.grove_shift_meter += amount

        if self.grove_shift_meter >= GROVE_SHIFT_MAX:
            self.grove_shift_meter = GROVE_SHIFT_MAX
            self.start_claimed_transition(reason="meter")

    # -----------------------------
    # Mini-game trigger and reward helpers
    # -----------------------------

    def schedule_next_mini_game_trigger(self, min_seconds=5, max_seconds=10):
        """
        Schedules the next mini-game trigger.

        This keeps mini-game selection random, but prevents the same mini-game from
        appearing more than twice in a row.
        """
        mini_game_options = [
            SIGILS_ECHO,
            STARLIGHT_CROSSING,
            CANOPY_CASCADE,
        ]

        chosen_mini_game = random.choice(mini_game_options)

        # Prevent the same mini-game from appearing 3+ times in a row.
        if (
            self.last_mini_game_type is not None
            and self.same_mini_game_streak >= 2
            and chosen_mini_game == self.last_mini_game_type
        ):
            alternate_options = [
                mini_game
                for mini_game in mini_game_options
                if mini_game != self.last_mini_game_type
            ]

            if alternate_options:
                chosen_mini_game = random.choice(alternate_options)

        if chosen_mini_game == self.last_mini_game_type:
            self.same_mini_game_streak += 1
        else:
            self.same_mini_game_streak = 1

        self.last_mini_game_type = chosen_mini_game
        self.active_mini_game_type = chosen_mini_game

        self.mini_game_trigger_available = False
        self.mini_game_trigger_spawned = False
        self.mini_game_trigger_rect = None
        self.mini_game_trigger_spawn_timer = random.randint(
            FPS * min_seconds,
            FPS * max_seconds,
        )

    def check_mini_game_trigger(self):
        """Starts the chosen mini-game when the trigger is touched."""
        if not self.mini_game_trigger_available:
            return

        if not self.mini_game_trigger_rect:
            return

        human_touched = self.player.rect.colliderect(self.mini_game_trigger_rect)
        fox_touched = self.fox.rect.colliderect(self.mini_game_trigger_rect)

        if not human_touched and not fox_touched:
            return

        if fox_touched and not human_touched:
            started_by = "fox"
        else:
            started_by = "human"

        if self.active_mini_game_type == STARLIGHT_CROSSING:
            self.start_starlight_crossing(started_by=started_by)
        elif self.active_mini_game_type == CANOPY_CASCADE:
            self.start_canopy_cascade(started_by=started_by)
        else:
            self.start_sigils_echo(started_by=started_by)

    def apply_mini_game_reward(self, reward_id):
        """Applies a reward returned by any integrated mini-game."""
        if reward_id == REWARD_GROVE_CALM:
            self.grove_shift_meter = max(
                0,
                self.grove_shift_meter - REWARD_METER_AMOUNT,
            )
            self.ui.show_toast("Grove Calm: Shift reduced", duration=120)

        elif reward_id == REWARD_LANTERN_SHIELD:
            self.lantern_shield_active = True
            self.ui.show_toast("Lantern Shield gained", duration=120)

        elif reward_id == REWARD_FOX_BANISH:
            self.fox_banish_timer = REWARD_FOX_BANISH_FRAMES
            self.clear_fox_ai_path()

            if hasattr(self.fox, "enter_recover_state"):
                self.fox.enter_recover_state()

            self.ui.show_toast("Fox Banish activated", duration=120)

        elif reward_id == REWARD_MISCHIEF_SURGE:
            self.add_grove_shift(REWARD_METER_AMOUNT)
            self.ui.show_toast("Mischief Surge: Shift increased", duration=120)

        elif reward_id == REWARD_SHADOW_RUSH:
            self.shadow_rush_timer = REWARD_SHADOW_RUSH_FRAMES
            self.ui.show_toast("Shadow Rush: fox empowered", duration=120)

        elif reward_id == REWARD_PORTAL_FLICKER:
            if self.portal_is_active:
                self.portal_flicker_timer = REWARD_PORTAL_FLICKER_FRAMES
                self.ui.show_toast("Portal Flicker: portal destabilized", duration=120)
            else:
                self.pending_portal_flicker = True
                self.ui.show_toast("Portal Flicker stored", duration=120)

    def update_mini_game_trigger_spawn(self):
        """Reveals the scheduled mini-game trigger after the level has started."""
        if self.mini_game_trigger_spawned:
            return

        if self.state != PLAYING:
            return

        if self.shards_collected < 1:
            return

        if self.mini_game_trigger_spawn_timer > 0:
            self.mini_game_trigger_spawn_timer -= 1
            return

        self.mini_game_trigger_rect = self.create_mini_game_trigger_rect()
        self.mini_game_trigger_available = True
        self.mini_game_trigger_spawned = True

        if self.active_mini_game_type == STARLIGHT_CROSSING:
            self.ui.show_toast("A Starlight Circuit has appeared...", duration=110)
        elif self.active_mini_game_type == CANOPY_CASCADE:
            self.ui.show_toast("A Canopy Crest has appeared...", duration=110)
        else:
            self.ui.show_toast("An Echo Sigil has appeared...", duration=110)

    # -----------------------------
    # Portal / fox safety
    # -----------------------------

    def apply_portal_guard_to_fox(self):
        """Prevents the fox from camping the active portal without freezing the AI."""
        if not self.portal_is_active:
            return

        if not self.maze.door_rect:
            return

        if not self.is_fox_inside_portal_guard():
            return

        self.clear_fox_ai_path()

        if self.game_mode == SINGLE_PLAYER:
            moved_to_safe_tile = self.place_fox_on_safe_portal_guard_tile()

            if moved_to_safe_tile:
                if hasattr(self.fox, "enter_recover_state"):
                    self.fox.enter_recover_state()
            else:
                # Fallback: push instead of forcing recover forever.
                self.push_fox_out_of_portal_guard()

            return

        self.push_fox_out_of_portal_guard()

    def push_fox_out_of_portal_guard(self):
        """Pushes the fox away from the portal guard zone."""
        portal_center_x, portal_center_y = self.maze.door_rect.center
        fox_center_x, fox_center_y = self.fox.rect.center

        dx = fox_center_x - portal_center_x
        dy = fox_center_y - portal_center_y

        distance = math.hypot(dx, dy)

        if distance == 0:
            dx = 1
            dy = 0
            distance = 1

        direction_x = dx / distance
        direction_y = dy / distance

        depth_ratio = 1 - (distance / PORTAL_GUARD_RADIUS)
        push_strength = PORTAL_REPEL_STRENGTH + int(depth_ratio * 8)

        push_x = int(direction_x * push_strength)
        push_y = int(direction_y * push_strength)

        if push_x == 0 and direction_x != 0:
            push_x = 1 if direction_x > 0 else -1

        if push_y == 0 and direction_y != 0:
            push_y = 1 if direction_y > 0 else -1

        self.move_fox_with_wall_safety(push_x, push_y)

    def clear_fox_ai_path(self):
        """Clears fox AI path data so it recalculates."""
        if hasattr(self.fox, "path"):
            self.fox.path = []

        if hasattr(self.fox, "current_target_tile"):
            self.fox.current_target_tile = None

        if hasattr(self.fox, "patrol_target_tile"):
            self.fox.patrol_target_tile = None

    def is_fox_inside_portal_guard(self):
        """Returns True if the fox is inside the active portal guard zone."""
        if not self.portal_is_active:
            return False

        if not self.maze.door_rect:
            return False

        portal_x, portal_y = self.maze.door_rect.center
        fox_x, fox_y = self.fox.rect.center

        distance = math.hypot(fox_x - portal_x, fox_y - portal_y)

        return distance < PORTAL_GUARD_RADIUS

    def place_fox_on_safe_portal_guard_tile(self):
        """Moves the fox to a safe open tile outside the portal guard zone."""
        if not self.maze.door_rect:
            return False

        portal_x, portal_y = self.maze.door_rect.center
        fox_x, fox_y = self.fox.rect.center
        player_x, player_y = self.player.rect.center

        best_tile = None
        best_score = None

        for row_index, row in enumerate(self.maze.layout):
            for col_index, tile in enumerate(row):
                if tile != "0":
                    continue

                tile_center_x = col_index * TILE_SIZE + TILE_SIZE // 2
                tile_center_y = row_index * TILE_SIZE + TILE_SIZE // 2

                distance_from_portal = math.hypot(
                    tile_center_x - portal_x,
                    tile_center_y - portal_y,
                )

                if distance_from_portal < PORTAL_GUARD_RADIUS + TILE_SIZE * 2:
                    continue

                distance_from_player = math.hypot(
                    tile_center_x - player_x,
                    tile_center_y - player_y,
                )

                if distance_from_player < TILE_SIZE * 3:
                    continue

                distance_from_fox = math.hypot(
                    tile_center_x - fox_x,
                    tile_center_y - fox_y,
                )

                score = distance_from_fox + distance_from_portal * 0.08

                if best_score is None or score < best_score:
                    best_score = score
                    best_tile = (col_index, row_index)

        if best_tile is None:
            return False

        col, row = best_tile

        self.fox.rect.x = col * TILE_SIZE + (TILE_SIZE - FOX_COLLISION_SIZE) // 2
        self.fox.rect.y = row * TILE_SIZE + (TILE_SIZE - FOX_COLLISION_SIZE) // 2

        self.fox.sync_position_from_rect()
        return True

    def move_fox_with_wall_safety(self, dx, dy):
        """Moves the fox by a small push amount while respecting walls."""
        original_position = self.fox.rect.copy()

        self.fox.rect.x += dx
        self.fox.rect.y += dy

        if not self.fox.is_colliding(self.wall_rects):
            self.fox.sync_position_from_rect()
            return

        self.fox.rect = original_position.copy()
        self.fox.rect.x += dx

        if self.fox.is_colliding(self.wall_rects):
            self.fox.rect = original_position.copy()
        else:
            original_position = self.fox.rect.copy()

        self.fox.rect.y += dy

        if self.fox.is_colliding(self.wall_rects):
            self.fox.rect = original_position.copy()

        self.fox.sync_position_from_rect()

    # -----------------------------
    # Gameplay actions
    # -----------------------------

    def collect_shard(self, shard):
        """Handles Grove Shard collection."""
        shard.collected = True
        self.shards_collected += 1

        self.ui.create_shard_collection_feedback(shard.rect.center)

        if self.shards_collected >= SHARD_COUNT and not self.portal_is_active:
            self.activate_portal()

    def activate_portal(self):
        """Activates the portal after all Grove Shards are collected."""
        self.portal_is_active = True

        if self.maze.door_rect:
            self.ui.create_portal_activation_feedback(self.maze.door_rect.center)
        else:
            self.ui.show_toast("Portal Awakened")

        if self.pending_portal_flicker:
            self.pending_portal_flicker = False
            self.portal_flicker_timer = REWARD_PORTAL_FLICKER_FRAMES
            self.ui.show_toast("Portal Flicker activates!", duration=110)

    def lose_life(self):
        """Removes one player life and triggers claimed transition at zero."""
        if self.state != PLAYING:
            return

        if self.player_lives <= 0:
            return

        self.player_lives -= 1

        if self.player_lives > 0:
            self.ui.show_toast("Life Lost", duration=90)
        else:
            self.start_claimed_transition(reason="lives")

    def reset_positions_after_fox_catch(self):
        """Resets player and fox positions after the fox catches the player."""
        self.player.rect.topleft = (PLAYER_START_X, PLAYER_START_Y)
        self.fox = self.create_fox()
        self.fox_catch_cooldown = FOX_CATCH_COOLDOWN_FRAMES
        self.fox.enter_recover_state()

    def check_human_win_condition(self):
        """Checks whether the player can escape through the portal."""
        if not self.maze.door_rect:
            return

        if not self.player.rect.colliderect(self.maze.door_rect):
            return

        if self.portal_is_active:
            if self.portal_flicker_timer > 0:
                self.ui.show_toast("Portal flickering — hold on!", duration=70)
                return

            self.start_escape_transition()
        else:
            self.ui.show_toast("Portal sealed — collect all shards.", duration=95)

    # -----------------------------
    # Draw routing
    # -----------------------------

    def draw(self):
        """Draws the correct screen for the current state."""
        if self.state == START:
            self.draw_start_screen()

        elif self.state == STORY:
            self.draw_story_screen()

        elif self.state == MODE_SELECT:
            self.draw_mode_select_screen()

        elif self.state == TRANSITION:
            self.draw_transition_screen()

        elif self.state == PLAYING:
            self.draw_gameplay_screen()

        elif self.state == SIGILS_ECHO:
            self.draw_gameplay_screen()
            self.draw_sigils_echo_layer()

        elif self.state == STARLIGHT_CROSSING:
            self.draw_starlight_crossing_layer()

        elif self.state == CANOPY_CASCADE:
            self.draw_canopy_cascade_layer()

        elif self.state == CLAIMED_TRANSITION:
            self.draw_gameplay_screen()
            self.draw_claimed_transition()

        elif self.state == ESCAPE_TRANSITION:
            self.draw_gameplay_screen()
            self.draw_escape_transition()

        elif self.state == HUMAN_WIN:
            self.draw_human_win_screen()

        elif self.state == LOSE:
            self.draw_gameplay_screen()
            self.draw_lose_screen()

        pygame.display.flip()
        self.clock.tick(FPS)

    # -----------------------------
    # Menu / story drawing
    # -----------------------------
    def draw_transition_screen(self):
        """
        Draws the Grove shifting transition without flashing the maze too early.

        During fade-in, the mode select screen stays underneath the mist.
        During hold and fade-out, the new gameplay maze is shown underneath.
        """
        if self.transition_direction == "fade_in":
            self.draw_mode_select_screen()
        else:
            self.draw_gameplay_screen()

        self.ui.draw_transition(self.screen, self.transition_alpha)

    def draw_start_screen(self):
        """Draws the title screen."""
        self.draw_title_screen_background()

        self.start_button.draw(self.screen)
        self.how_to_play_button.draw(self.screen)
        self.quit_button.draw(self.screen)

    def draw_mode_select_screen(self):
        """Draws the mode selection screen."""
        self.draw_title_screen_background()

        self.single_player_button.draw(self.screen)
        self.multiplayer_button.draw(self.screen)

        if not SINGLE_PLAYER_BUTTON_IMAGE.exists():
            self.draw_button_center_label(
                self.single_player_button.rect,
                "Single Player",
            )

        if not MULTIPLAYER_BUTTON_IMAGE.exists():
            self.draw_button_center_label(
                self.multiplayer_button.rect,
                "Local Multiplayer",
            )

        back_text = self.tiny_font.render(
            "Press ESC to return",
            True,
            (20, 18, 24),
        )
        back_rect = back_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 42))
        self.screen.blit(back_text, back_rect)

    def draw_button_center_label(self, button_rect, label):
        """Draws readable fallback text centered over a button."""
        label_surface = self.small_font.render(label, True, TEXT_COLOR)
        shadow_surface = self.small_font.render(label, True, (45, 35, 50))

        label_rect = label_surface.get_rect(center=button_rect.center)
        shadow_rect = shadow_surface.get_rect(
            center=(button_rect.centerx + 2, button_rect.centery + 2)
        )

        self.screen.blit(shadow_surface, shadow_rect)
        self.screen.blit(label_surface, label_rect)

    def draw_story_screen(self):
        """Draws the full-screen How to Play screen."""
        if self.how_to_play_fullscreen:
            self.screen.blit(self.how_to_play_fullscreen, (0, 0))
        else:
            self.draw_how_to_play_fallback()

    def draw_how_to_play_fallback(self):
        """Draws fallback How to Play text if the scroll image is missing."""
        title = self.large_font.render("How to Play", True, TEXT_COLOR)
        instruction_1 = self.medium_font.render("Move with W A S D", True, TEXT_COLOR)
        instruction_2 = self.medium_font.render(
            "Collect all Grove Shards",
            True,
            TEXT_COLOR,
        )
        instruction_3 = self.medium_font.render(
            "Reach the portal to escape",
            True,
            TEXT_COLOR,
        )
        instruction_4 = self.small_font.render(
            "Press SPACE to choose a mode",
            True,
            TEXT_COLOR,
        )
        instruction_5 = self.small_font.render("Press ESC to return", True, TEXT_COLOR)

        center_x = SCREEN_WIDTH // 2

        self.screen.blit(title, title.get_rect(center=(center_x, 190)))
        self.screen.blit(instruction_1, instruction_1.get_rect(center=(center_x, 280)))
        self.screen.blit(instruction_2, instruction_2.get_rect(center=(center_x, 335)))
        self.screen.blit(instruction_3, instruction_3.get_rect(center=(center_x, 390)))
        self.screen.blit(instruction_4, instruction_4.get_rect(center=(center_x, 470)))
        self.screen.blit(instruction_5, instruction_5.get_rect(center=(center_x, 515)))

    # -----------------------------
    # Gameplay drawing
    # -----------------------------

    def draw_gameplay_screen(self):
        """Draws active gameplay."""
        self.draw_game_background()

        visible_portal_active = (
            self.portal_is_active
            and self.portal_flicker_timer <= 0
        )

        self.maze.draw(self.screen, portal_is_active=visible_portal_active)

        for shard in self.shards:
            shard.draw(self.screen)

        self.draw_mini_game_trigger()

        self.fox.draw(self.screen)
        self.player.draw(self.screen)

        self.ui.draw_gameplay_ui(
            screen=self.screen,
            shards_collected=self.shards_collected,
            portal_is_active=self.portal_is_active,
            player=self.player,
            player_lives=self.player_lives,
            max_lives=PLAYER_MAX_LIVES,
            grove_shift_meter=self.grove_shift_meter,
            grove_shift_max=GROVE_SHIFT_MAX,
            portal_rect=self.maze.door_rect,
            fox_banish_timer=self.fox_banish_timer,
            shadow_rush_timer=self.shadow_rush_timer,
            portal_flicker_timer=self.portal_flicker_timer,
            fps=FPS,
        )

    def draw_mini_game_trigger(self):
        """Draws the currently selected mini-game trigger in the maze."""
        if not self.mini_game_trigger_available:
            return

        if not self.mini_game_trigger_rect:
            return

        center = self.mini_game_trigger_rect.center

        glow_surface = pygame.Surface(
            (ECHO_SIGIL_SIZE * 4, ECHO_SIGIL_SIZE * 4),
            pygame.SRCALPHA,
        )

        glow_center = (
            glow_surface.get_width() // 2,
            glow_surface.get_height() // 2,
        )

        pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.006)

        pygame.draw.circle(
            glow_surface,
            (180, 120, 255, int(60 + 35 * pulse)),
            glow_center,
            ECHO_SIGIL_SIZE + 14,
        )

        pygame.draw.circle(
            glow_surface,
            (110, 245, 230, int(70 + 35 * pulse)),
            glow_center,
            ECHO_SIGIL_SIZE // 2 + 10,
        )

        glow_rect = glow_surface.get_rect(center=center)
        self.screen.blit(glow_surface, glow_rect)

        if self.active_mini_game_type == STARLIGHT_CROSSING:
            trigger_image = self.starlight_trigger_image
        elif self.active_mini_game_type == CANOPY_CASCADE:
            trigger_image = self.canopy_trigger_image
        else:
            trigger_image = self.echo_sigil_image

        if trigger_image:
            sigil_rect = trigger_image.get_rect(center=center)
            self.screen.blit(trigger_image, sigil_rect)
        else:
            pygame.draw.circle(
                self.screen,
                (245, 225, 255),
                center,
                ECHO_SIGIL_SIZE // 2,
            )
            pygame.draw.circle(
                self.screen,
                (95, 55, 150),
                center,
                ECHO_SIGIL_SIZE // 2,
                3,
            )
            sigil_text = self.tiny_font.render("✦", True, (55, 30, 90))
            sigil_rect = sigil_text.get_rect(center=center)
            self.screen.blit(sigil_text, sigil_rect)

    # -----------------------------
    # Mini-game drawing layers
    # -----------------------------

    def draw_sigils_echo_layer(self):
        """
        Draws The Sigil's Echo over the paused maze.

        The mini-game file owns all of its own visuals, including the rotating wall
        intro, instruction wall, pattern reveal, scoring, and reward selection.
        """
        if self.sigils_echo:
            self.sigils_echo.draw(self.screen)

    def draw_starlight_crossing_layer(self):
        """Draws Starlight Crossing over the paused maze."""
        if self.starlight_crossing:
            self.starlight_crossing.draw(self.screen)

    def draw_canopy_cascade_layer(self):
        """Draws Canopy Cascade over the paused maze."""
        if self.canopy_cascade:
            self.canopy_cascade.draw(self.screen)
    # -----------------------------
    # Claimed / lose transition
    # -----------------------------

    def draw_claimed_transition(self):
        """Draws the claimed transition."""
        progress = min(self.claimed_timer / CLAIMED_TRANSITION_FRAMES, 1)

        self.draw_vines_overlay_transition(progress)
        self.draw_claimed_darkness(progress)
        self.draw_claimed_transition_text(progress)

    def draw_vines_overlay_transition(self, progress):
        """Draws vines first and keeps them visible for the whole transition."""
        if not self.vines_overlay_image:
            return

        vine_progress = max(0, min(progress / 0.40, 1))

        if vine_progress <= 0:
            return

        alpha = int(245 * vine_progress)

        scale_amount = 1.07 - (0.07 * vine_progress)
        scaled_width = int(SCREEN_WIDTH * scale_amount)
        scaled_height = int(SCREEN_HEIGHT * scale_amount)

        scaled_vines = pygame.transform.smoothscale(
            self.vines_overlay_image,
            (scaled_width, scaled_height),
        )
        scaled_vines.set_alpha(alpha)

        vine_rect = scaled_vines.get_rect(
            center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        )

        self.screen.blit(scaled_vines, vine_rect)

    def draw_claimed_darkness(self, progress):
        """Darkens the screen after vines begin appearing."""
        darkness_progress = max(0, min((progress - 0.18) / 0.50, 1))

        if darkness_progress <= 0:
            return

        overlay_alpha = int(165 * darkness_progress)
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((7, 9, 16, overlay_alpha))
        self.screen.blit(overlay, (0, 0))

    def draw_claimed_transition_text(self, progress):
        """Shows the claimed message after vines and darkness."""
        text_progress = max(0, min((progress - 0.56) / 0.28, 1))

        if text_progress <= 0:
            return

        text_alpha = int(255 * text_progress)
        self.draw_claimed_text(text_alpha)

    def draw_claimed_text(self, text_alpha=255):
        """Draws the claimed text used by both transition and final lose screen."""
        title_line_1 = self.large_font.render("The Grove", True, TEXT_COLOR)
        title_line_2 = self.large_font.render("Has Claimed You", True, TEXT_COLOR)
        subtitle = self.small_font.render(
            "Your light fades within the maze...",
            True,
            TEXT_COLOR,
        )

        shadow_1 = self.large_font.render("The Grove", True, (10, 10, 10))
        shadow_2 = self.large_font.render("Has Claimed You", True, (10, 10, 10))
        shadow_3 = self.small_font.render(
            "Your light fades within the maze...",
            True,
            (10, 10, 10),
        )

        surfaces = [
            title_line_1,
            title_line_2,
            subtitle,
            shadow_1,
            shadow_2,
            shadow_3,
        ]

        for surface in surfaces:
            surface.set_alpha(text_alpha)

        center_x = SCREEN_WIDTH // 2
        center_y = SCREEN_HEIGHT // 2

        title1_rect = title_line_1.get_rect(center=(center_x, center_y - 85))
        title2_rect = title_line_2.get_rect(center=(center_x, center_y - 20))
        subtitle_rect = subtitle.get_rect(center=(center_x, center_y + 55))

        shadow_offset = 3

        self.screen.blit(
            shadow_1,
            (title1_rect.x + shadow_offset, title1_rect.y + shadow_offset),
        )
        self.screen.blit(
            shadow_2,
            (title2_rect.x + shadow_offset, title2_rect.y + shadow_offset),
        )
        self.screen.blit(
            shadow_3,
            (subtitle_rect.x + shadow_offset, subtitle_rect.y + shadow_offset),
        )

        self.screen.blit(title_line_1, title1_rect)
        self.screen.blit(title_line_2, title2_rect)
        self.screen.blit(subtitle, subtitle_rect)

    def draw_lose_screen(self):
        """Draws the final claimed screen using the same vine overlay style."""
        self.draw_vines_overlay_transition(1)
        self.draw_claimed_darkness(1)
        self.draw_claimed_text(255)

        restart = self.small_font.render(
            "Press R to choose a mode",
            True,
            TEXT_COLOR,
        )
        back_text = self.tiny_font.render(
            "Press ESC to return to the main menu",
            True,
            TEXT_COLOR,
        )

        restart_shadow = self.small_font.render(
            "Press R to choose a mode",
            True,
            (10, 10, 10),
        )
        back_shadow = self.tiny_font.render(
            "Press ESC to return to the main menu",
            True,
            (10, 10, 10),
        )

        center_x = SCREEN_WIDTH // 2
        center_y = SCREEN_HEIGHT // 2

        restart_rect = restart.get_rect(center=(center_x, center_y + 120))
        back_rect = back_text.get_rect(center=(center_x, center_y + 162))

        self.screen.blit(restart_shadow, (restart_rect.x + 2, restart_rect.y + 2))
        self.screen.blit(back_shadow, (back_rect.x + 2, back_rect.y + 2))

        self.screen.blit(restart, restart_rect)
        self.screen.blit(back_text, back_rect)

    # -----------------------------
    # Escape / human win transition
    # -----------------------------

    def draw_escape_transition(self):
        """Draws the human escape transition."""
        progress = min(self.escape_timer / ESCAPE_TRANSITION_FRAMES, 1)

        self.draw_portal_bloom(progress)
        self.draw_escape_particles(progress)
        self.draw_escape_brightness(progress)
        self.draw_escape_transition_text(progress)

    def draw_portal_bloom(self, progress):
        """Draws a stronger expanding magical bloom from the portal."""
        portal_x, portal_y = self.escape_portal_center
        bloom_progress = max(0, min(progress / 0.75, 1))

        if bloom_progress <= 0:
            return

        max_radius = int(max(SCREEN_WIDTH, SCREEN_HEIGHT) * 1.35)
        radius = int(max_radius * bloom_progress)

        glow_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

        for index in range(7):
            ring_radius = max(1, radius - index * 34)
            alpha = max(0, int((115 - index * 12) * (1 - bloom_progress * 0.20)))

            pygame.draw.circle(
                glow_surface,
                (105, 245, 225, alpha),
                (portal_x, portal_y),
                ring_radius,
            )

        inner_radius = int(70 + 180 * bloom_progress)

        pygame.draw.circle(
            glow_surface,
            (255, 225, 130, int(125 * (1 - bloom_progress * 0.10))),
            (portal_x, portal_y),
            inner_radius,
        )

        self.screen.blit(glow_surface, (0, 0))

    def draw_escape_particles(self, progress):
        """Draws deterministic sparkles radiating from the portal."""
        portal_x, portal_y = self.escape_portal_center
        particle_progress = max(0, min((progress - 0.05) / 0.85, 1))

        if particle_progress <= 0:
            return

        sparkle_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        particle_count = 36

        for index in range(particle_count):
            angle = (index / particle_count) * math.tau
            wave = math.sin((progress * 8) + index) * 18
            distance = (80 + index % 7 * 18) + particle_progress * (280 + wave)

            x = int(portal_x + math.cos(angle) * distance)
            y = int(portal_y + math.sin(angle) * distance)

            if x < -20 or x > SCREEN_WIDTH + 20 or y < -20 or y > SCREEN_HEIGHT + 20:
                continue

            size = 3 + (index % 3)
            alpha = int(210 * (1 - max(0, particle_progress - 0.65) / 0.35))

            if index % 2 == 0:
                color = (125, 245, 230, alpha)
            else:
                color = (255, 225, 145, alpha)

            pygame.draw.circle(sparkle_surface, color, (x, y), size)
            pygame.draw.line(
                sparkle_surface,
                color,
                (x - size * 2, y),
                (x + size * 2, y),
                1,
            )
            pygame.draw.line(
                sparkle_surface,
                color,
                (x, y - size * 2),
                (x, y + size * 2),
                1,
            )

        self.screen.blit(sparkle_surface, (0, 0))

    def draw_escape_brightness(self, progress):
        """Brightens the screen with a warm golden wash."""
        brightness_progress = max(0, min((progress - 0.22) / 0.58, 1))

        if brightness_progress <= 0:
            return

        overlay_alpha = int(215 * brightness_progress)

        light_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        light_overlay.fill((255, 232, 185, overlay_alpha))
        self.screen.blit(light_overlay, (0, 0))

    def draw_escape_transition_text(self, progress):
        """Fades in the human escape message and final instructions."""
        text_progress = max(0, min((progress - 0.58) / 0.28, 1))

        if text_progress <= 0:
            return

        text_alpha = int(255 * text_progress)
        self.draw_human_win_text(text_alpha)

    def draw_human_win_screen(self):
        """Draws the final human win screen without popping back to gameplay."""
        golden_background = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        golden_background.fill((245, 214, 150))
        self.screen.blit(golden_background, (0, 0))

        self.draw_portal_bloom(1)
        self.draw_escape_brightness(1)
        self.draw_human_win_text(255)

    def draw_human_win_text(self, text_alpha=255):
        """Draws readable final win text."""
        main_text_color = (35, 24, 10)
        shadow_color = (255, 236, 170)

        title = self.large_font.render("You Escaped", True, main_text_color)
        subtitle = self.medium_font.render("The Grove Releases You", True, main_text_color)
        small_text = self.small_font.render(
            "The portal opens beyond the shifting trees...",
            True,
            main_text_color,
        )
        restart = self.small_font.render("Press R to choose a mode", True, main_text_color)
        back_text = self.tiny_font.render(
            "Press ESC to return to the main menu",
            True,
            main_text_color,
        )

        shadow_title = self.large_font.render("You Escaped", True, shadow_color)
        shadow_subtitle = self.medium_font.render("The Grove Releases You", True, shadow_color)
        shadow_small = self.small_font.render(
            "The portal opens beyond the shifting trees...",
            True,
            shadow_color,
        )
        shadow_restart = self.small_font.render("Press R to choose a mode", True, shadow_color)
        shadow_back = self.tiny_font.render(
            "Press ESC to return to the main menu",
            True,
            shadow_color,
        )

        surfaces = [
            title,
            subtitle,
            small_text,
            restart,
            back_text,
            shadow_title,
            shadow_subtitle,
            shadow_small,
            shadow_restart,
            shadow_back,
        ]

        for surface in surfaces:
            surface.set_alpha(text_alpha)

        center_x = SCREEN_WIDTH // 2
        center_y = SCREEN_HEIGHT // 2
        shadow_offset = 3

        title_rect = title.get_rect(center=(center_x, center_y - 120))
        subtitle_rect = subtitle.get_rect(center=(center_x, center_y - 55))
        small_rect = small_text.get_rect(center=(center_x, center_y + 10))
        restart_rect = restart.get_rect(center=(center_x, center_y + 105))
        back_rect = back_text.get_rect(center=(center_x, center_y + 145))

        self.screen.blit(
            shadow_title,
            (title_rect.x + shadow_offset, title_rect.y + shadow_offset),
        )
        self.screen.blit(
            shadow_subtitle,
            (subtitle_rect.x + shadow_offset, subtitle_rect.y + shadow_offset),
        )
        self.screen.blit(
            shadow_small,
            (small_rect.x + shadow_offset, small_rect.y + shadow_offset),
        )
        self.screen.blit(
            shadow_restart,
            (restart_rect.x + shadow_offset, restart_rect.y + shadow_offset),
        )
        self.screen.blit(
            shadow_back,
            (back_rect.x + shadow_offset, back_rect.y + shadow_offset),
        )

        self.screen.blit(title, title_rect)
        self.screen.blit(subtitle, subtitle_rect)
        self.screen.blit(small_text, small_rect)
        self.screen.blit(restart, restart_rect)
        self.screen.blit(back_text, back_rect)


    # -----------------------------
    # Shared backgrounds
    # -----------------------------

    def draw_title_screen_background(self):
        """Draws the title background or fallback color."""
        self.screen.fill(BACKGROUND_COLOR)

        if self.title_screen_background:
            self.screen.blit(self.title_screen_background, (0, 0))

    def draw_game_background(self):
        """Draws the gameplay background."""
        self.screen.fill(BACKGROUND_COLOR)

        if self.background_image:
            self.screen.blit(self.background_image, (0, 0))

        if GAMEPLAY_BACKGROUND_SOFTEN_ALPHA > 0:
            soften_layer = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            soften_layer.set_alpha(GAMEPLAY_BACKGROUND_SOFTEN_ALPHA)
            soften_layer.fill((235, 245, 235))
            self.screen.blit(soften_layer, (0, 0))
