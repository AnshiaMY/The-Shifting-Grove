"""
fox.py

Fox guardian controller for The Shifting Grove.

This module defines the fox character used in both single-player and local
multiplayer modes. In local multiplayer, the fox is controlled with the arrow
keys. In single-player, the fox uses a state-based AI system with BFS
pathfinding to patrol, chase, search, intercept objectives, seek mini-game
triggers, and recover after forced repositioning.

The fox intentionally uses a smaller collision rectangle than its visible
sprite so movement through maze corridors feels fair while the character still
looks polished on screen.
"""

import math
import random
from collections import deque

import pygame

from asset_loader import load_image
from settings import (
    FOX_AI_SPEED,
    FOX_COLLISION_SIZE,
    FOX_DETECTION_RADIUS_TILES,
    FOX_IMAGE,
    FOX_MEMORY_FRAMES,
    FOX_PATH_RECALCULATE_FRAMES,
    FOX_PATROL_RECALCULATE_FRAMES,
    FOX_PREDICT_TILES,
    FOX_RECOVER_FRAMES,
    FOX_SPEED,
    PORTAL_GUARD_RADIUS,
    TILE_SIZE,
)


class Fox:
    """Fox character with player-controlled and AI-controlled behavior."""

    PATROL = "patrol"
    CHASE = "chase"
    SEARCH = "search"
    INTERCEPT = "intercept"
    SEEK_MINI_GAME = "seek_mini_game"
    RECOVER = "recover"

    CORNER_ASSIST_DISTANCE = 7
    SPRITE_DRAW_HEIGHT = 70

    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)

        self.rect = pygame.Rect(
            round(self.x),
            round(self.y),
            FOX_COLLISION_SIZE,
            FOX_COLLISION_SIZE,
        )

        self.speed = FOX_SPEED
        self.ai_speed = FOX_AI_SPEED

        raw_fox_image = load_image(FOX_IMAGE, use_alpha=True)
        self.image = self.scale_image_to_height(
            raw_fox_image,
            self.SPRITE_DRAW_HEIGHT,
        )

        # Pathfinding state used by the single-player AI.
        self.path = []
        self.current_target_tile = None
        self.path_recalculate_timer = 0

        # Current AI behavior state.
        self.state = self.PATROL
        self.memory_timer = 0
        self.recover_timer = 0
        self.last_known_player_tile = None

        # Patrol targeting state.
        self.patrol_target_tile = None
        self.patrol_recalculate_timer = 0

        # Last player position used for short movement prediction.
        self.previous_player_center = None

    # -----------------------------
    # Position helpers
    # -----------------------------

    def sync_rect_to_position(self):
        """Syncs the collision rectangle from floating-point coordinates."""
        self.rect.x = round(self.x)
        self.rect.y = round(self.y)

    def sync_position_from_rect(self):
        """Syncs floating-point coordinates from the collision rectangle."""
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)

    def get_draw_rect(self):
        """Returns the sprite draw rectangle centered over the collision rect."""
        if self.image:
            return self.image.get_rect(center=self.rect.center)

        return self.rect

    # -----------------------------
    # Public update methods
    # -----------------------------

    def enter_recover_state(self):
        """
        Places the fox into a short recover state.

        This prevents the fox from instantly catching the player again after a
        reset or forced correction.
        """
        self.state = self.RECOVER
        self.recover_timer = FOX_RECOVER_FRAMES
        self.path = []
        self.current_target_tile = None
        self.patrol_target_tile = None

    def update_multiplayer(self, wall_rects):
        """Updates fox movement for local multiplayer using arrow keys."""
        keys = pygame.key.get_pressed()

        dx = 0
        dy = 0

        if keys[pygame.K_LEFT]:
            dx -= self.speed
        if keys[pygame.K_RIGHT]:
            dx += self.speed
        if keys[pygame.K_UP]:
            dy -= self.speed
        if keys[pygame.K_DOWN]:
            dy += self.speed

        self.move(dx, dy, wall_rects)

    def update_ai(
        self,
        player,
        maze_layout,
        wall_rects,
        shards=None,
        portal_is_active=False,
        portal_rect=None,
        shards_collected=0,
        mini_game_trigger_rect=None,
        mini_game_available=False,
        fox_urgency=0,
    ):
        """
        Updates fox behavior in single-player mode.

        The AI selects a behavior state, chooses a target tile, computes a BFS
        path, and moves through the maze while respecting wall collisions and
        portal anti-camping rules.
        """
        if shards is None:
            shards = []

        self.update_ai_state(
            player=player,
            maze_layout=maze_layout,
            shards=shards,
            portal_is_active=portal_is_active,
            portal_rect=portal_rect,
            shards_collected=shards_collected,
            mini_game_trigger_rect=mini_game_trigger_rect,
            mini_game_available=mini_game_available,
            fox_urgency=fox_urgency,
        )

        if self.state == self.RECOVER:
            return

        target_tile = self.choose_target_tile(
            player=player,
            maze_layout=maze_layout,
            shards=shards,
            portal_is_active=portal_is_active,
            portal_rect=portal_rect,
            shards_collected=shards_collected,
            mini_game_trigger_rect=mini_game_trigger_rect,
        )

        self.follow_target_tile(
            target_tile=target_tile,
            maze_layout=maze_layout,
            wall_rects=wall_rects,
            portal_is_active=portal_is_active,
            portal_rect=portal_rect,
        )

    # -----------------------------
    # AI state logic
    # -----------------------------

    def update_ai_state(
        self,
        player,
        maze_layout,
        shards,
        portal_is_active,
        portal_rect,
        shards_collected,
        mini_game_trigger_rect,
        mini_game_available,
        fox_urgency,
    ):
        """
        Chooses the fox's current behavior state.

        Priority:
        1. Recover after catching or being corrected.
        2. Chase if the player is detected.
        3. Intercept when the portal is active.
        4. Search last known player location.
        5. Intercept shard routes if the player has started collecting.
        6. Patrol otherwise.
        """
        if self.recover_timer > 0:
            self.recover_timer -= 1
            self.state = self.RECOVER
            return

        player_detected = self.can_detect_player(player)

        if player_detected:
            self.last_known_player_tile = self.get_predicted_player_tile(
                player,
                maze_layout,
            )
            self.memory_timer = FOX_MEMORY_FRAMES

        elif self.memory_timer > 0:
            self.memory_timer -= 1

        player_very_close = self.is_player_very_close(player)

        # Close player pressure should override strategic objectives. This
        # prevents the fox from ignoring a nearby player to chase a trigger.
        if player_detected or player_very_close:
            self.state = self.CHASE

        elif (
            mini_game_available
            and mini_game_trigger_rect is not None
            and fox_urgency >= 60
        ):
            self.state = self.SEEK_MINI_GAME

        elif portal_is_active and portal_rect is not None:
            self.state = self.INTERCEPT

        elif self.memory_timer > 0 and self.last_known_player_tile is not None:
            self.state = self.SEARCH

        elif shards_collected > 0 and self.has_uncollected_shards(shards):
            self.state = self.INTERCEPT

        else:
            self.state = self.PATROL

    def can_detect_player(self, player):
        """Returns True if the player is within the fox's detection range."""
        fox_x, fox_y = self.rect.center
        player_x, player_y = player.rect.center

        distance = math.hypot(fox_x - player_x, fox_y - player_y)
        detection_radius = FOX_DETECTION_RADIUS_TILES * TILE_SIZE

        return distance <= detection_radius

    def is_player_very_close(self, player):
        """
        Returns True if the player is close enough that chasing is better than
        switching to a strategic objective.
        """
        fox_x, fox_y = self.rect.center
        player_x, player_y = player.rect.center

        distance = math.hypot(fox_x - player_x, fox_y - player_y)

        return distance <= TILE_SIZE * 3

    def has_uncollected_shards(self, shards):
        """Returns True if any Grove Shards remain uncollected."""
        for shard in shards:
            if not shard.collected:
                return True

        return False

    # -----------------------------
    # AI target selection
    # -----------------------------

    def choose_target_tile(
        self,
        player,
        maze_layout,
        shards,
        portal_is_active,
        portal_rect,
        shards_collected,
        mini_game_trigger_rect=None,
    ):
        """Chooses the current target tile based on the fox's AI state."""
        if self.state == self.CHASE:
            if portal_is_active and portal_rect is not None:
                return self.choose_portal_safe_chase_tile(
                    player,
                    portal_rect,
                    maze_layout,
                )

            return self.get_predicted_player_tile(player, maze_layout)

        if self.state == self.SEARCH and self.last_known_player_tile is not None:
            return self.last_known_player_tile

        if self.state == self.SEEK_MINI_GAME and mini_game_trigger_rect is not None:
            return self.find_nearby_walkable_tile(
                self.get_tile_position(mini_game_trigger_rect.center),
                maze_layout,
            )

        if self.state == self.INTERCEPT:
            return self.choose_intercept_tile(
                player=player,
                maze_layout=maze_layout,
                shards=shards,
                portal_is_active=portal_is_active,
                portal_rect=portal_rect,
                shards_collected=shards_collected,
            )

        return self.choose_patrol_tile(maze_layout)

    def choose_intercept_tile(
        self,
        player,
        maze_layout,
        shards,
        portal_is_active,
        portal_rect,
        shards_collected,
    ):
        """
        Chooses an objective-aware intercept target.

        If the portal is active, the fox guards the route to the portal without
        entering the anti-camping zone.

        If the portal is not active, the fox pressures likely shard routes.
        """
        if portal_is_active and portal_rect is not None:
            return self.choose_portal_route_intercept_tile(
                player,
                portal_rect,
                maze_layout,
            )

        if shards_collected > 0 and self.has_uncollected_shards(shards):
            return self.choose_shard_route_intercept_tile(
                player,
                shards,
                maze_layout,
            )

        return self.get_predicted_player_tile(player, maze_layout)

    def choose_portal_route_intercept_tile(self, player, portal_rect, maze_layout):
        """
        Chooses a portal-route intercept tile without entering the portal guard.

        The fox should guard the route to the portal, not the portal itself.
        This prevents the AI from repeatedly walking into the anti-camping zone.
        """
        if portal_rect is None:
            return self.get_predicted_player_tile(player, maze_layout)

        player_tile = self.get_tile_position(player.rect.center)
        portal_tile = self.get_tile_position(portal_rect.center)

        path_to_portal = self.find_path_between(
            player_tile,
            portal_tile,
            maze_layout,
        )

        if not path_to_portal:
            return self.choose_portal_safe_chase_tile(
                player,
                portal_rect,
                maze_layout,
            )

        # Prefer a tile near the portal route, but safely outside the portal guard.
        for tile in reversed(path_to_portal):
            if self.is_tile_outside_portal_guard(
                tile,
                portal_rect,
                extra_buffer_tiles=2,
            ):
                return tile

        # Fallback: choose a safe route tile closer to the player side.
        for tile in path_to_portal:
            if self.is_tile_outside_portal_guard(
                tile,
                portal_rect,
                extra_buffer_tiles=2,
            ):
                return tile

        # Last fallback: choose a nearby legal tile instead of walking into portal.
        player_tile = self.get_tile_position(player.rect.center)
        safe_tile = self.find_nearby_portal_safe_tile(
            player_tile,
            portal_rect,
            maze_layout,
            extra_buffer_tiles=2,
        )

        if safe_tile is not None:
            return safe_tile

        return self.choose_patrol_tile(maze_layout)

    def choose_portal_safe_chase_tile(self, player, portal_rect, maze_layout):
        """
        Chases the human without choosing a target inside the portal guard.

        When the portal is active, the player may stand very close to the
        portal. A normal chase target would pull the fox into the protected
        anti-camping zone, causing the portal guard to push it out every frame.
        This chooses the closest legal tile near the player instead.
        """
        predicted_tile = self.get_predicted_player_tile(player, maze_layout)

        if (
            predicted_tile is not None
            and self.is_tile_outside_portal_guard(
                predicted_tile,
                portal_rect,
                extra_buffer_tiles=1,
            )
        ):
            return predicted_tile

        fox_tile = self.get_tile_position(self.rect.center)
        player_tile = self.get_tile_position(player.rect.center)

        path_to_player = self.find_path_between(
            fox_tile,
            player_tile,
            maze_layout,
        )

        # Choose the legal tile closest to the player. This lets the fox guard
        # the escape route without stepping into the portal itself.
        for tile in reversed(path_to_player):
            if self.is_tile_outside_portal_guard(
                tile,
                portal_rect,
                extra_buffer_tiles=1,
            ):
                return tile

        safe_tile = self.find_nearby_portal_safe_tile(
            player_tile,
            portal_rect,
            maze_layout,
            extra_buffer_tiles=1,
        )

        if safe_tile is not None:
            return safe_tile

        return self.choose_patrol_tile(maze_layout)

    def choose_shard_route_intercept_tile(self, player, shards, maze_layout):
        """
        Chooses a route toward an uncollected shard.

        This lets the fox pressure the player's objective without needing to
        know exactly where the player will go.
        """
        player_tile = self.get_tile_position(player.rect.center)

        best_path = None
        best_shard_tile = None

        for shard in shards:
            if shard.collected:
                continue

            shard_tile = self.get_tile_position(shard.rect.center)
            path = self.find_path_between(
                player_tile,
                shard_tile,
                maze_layout,
            )

            if not path:
                continue

            if best_path is None or len(path) < len(best_path):
                best_path = path
                best_shard_tile = shard_tile

        if not best_path:
            return self.get_predicted_player_tile(player, maze_layout)

        if len(best_path) >= 4:
            return best_path[min(3, len(best_path) - 1)]

        return best_shard_tile

    def choose_patrol_tile(self, maze_layout):
        """Chooses and maintains a random patrol target."""
        self.patrol_recalculate_timer -= 1

        if (
            self.patrol_target_tile is None
            or self.patrol_recalculate_timer <= 0
            or self.get_tile_position(self.rect.center) == self.patrol_target_tile
        ):
            self.patrol_target_tile = self.get_random_walkable_tile(maze_layout)
            self.patrol_recalculate_timer = FOX_PATROL_RECALCULATE_FRAMES

        return self.patrol_target_tile

    def get_predicted_player_tile(self, player, maze_layout):
        """
        Predicts a nearby future player tile based on recent movement.

        This makes the fox feel smarter without requiring unfair instant reaction.
        """
        current_center = player.rect.center

        if self.previous_player_center is None:
            self.previous_player_center = current_center
            return self.find_nearby_walkable_tile(
                self.get_tile_position(current_center),
                maze_layout,
            )

        previous_x, previous_y = self.previous_player_center
        current_x, current_y = current_center

        dx = current_x - previous_x
        dy = current_y - previous_y

        self.previous_player_center = current_center

        if dx == 0 and dy == 0:
            return self.find_nearby_walkable_tile(
                self.get_tile_position(current_center),
                maze_layout,
            )

        predicted_x = current_x + dx * FOX_PREDICT_TILES
        predicted_y = current_y + dy * FOX_PREDICT_TILES

        predicted_tile = self.get_tile_position((predicted_x, predicted_y))

        walkable_tile = self.find_nearby_walkable_tile(
            predicted_tile,
            maze_layout,
        )

        if walkable_tile is not None:
            return walkable_tile

        return self.find_nearby_walkable_tile(
            self.get_tile_position(current_center),
            maze_layout,
        )

    # -----------------------------
    # Path following
    # -----------------------------

    def follow_target_tile(
        self,
        target_tile,
        maze_layout,
        wall_rects,
        portal_is_active=False,
        portal_rect=None,
    ):
        """Follows a BFS path toward the selected target tile."""
        if target_tile is None:
            return

        avoiding_portal_guard = portal_is_active and portal_rect is not None

        if avoiding_portal_guard:
            safe_target_tile = self.find_nearby_portal_safe_tile(
                target_tile,
                portal_rect,
                maze_layout,
                extra_buffer_tiles=0,
            )

            if safe_target_tile is None:
                self.path = []
                self.current_target_tile = None
                return

            target_tile = safe_target_tile

        self.path_recalculate_timer -= 1

        current_tile = self.get_tile_position(self.rect.center)

        if (
            self.current_target_tile != target_tile
            or self.path_recalculate_timer <= 0
            or not self.path
        ):
            self.path = self.find_path_between(
                current_tile,
                target_tile,
                maze_layout,
                portal_rect=portal_rect,
                avoid_portal_guard=avoiding_portal_guard,
                extra_buffer_tiles=0,
            )

            # If the portal guard blocks the full path, still move as close as
            # legally possible instead of freezing or trying to enter the guard.
            if not self.path and avoiding_portal_guard:
                normal_path = self.find_path_between(
                    current_tile,
                    target_tile,
                    maze_layout,
                )
                safe_path_prefix = []

                for tile in normal_path:
                    if not self.is_tile_outside_portal_guard(
                        tile,
                        portal_rect,
                        extra_buffer_tiles=0,
                    ):
                        break

                    safe_path_prefix.append(tile)

                self.path = safe_path_prefix

            self.current_target_tile = target_tile
            self.path_recalculate_timer = FOX_PATH_RECALCULATE_FRAMES

        if not self.path:
            return

        # If the first path tile is the fox's current tile, skip it.
        if self.path and self.path[0] == current_tile:
            self.path.pop(0)

        if not self.path:
            return

        next_tile = self.path[0]

        if avoiding_portal_guard and not self.is_tile_outside_portal_guard(
            next_tile,
            portal_rect,
            extra_buffer_tiles=0,
        ):
            self.path = []
            self.current_target_tile = None
            return

        reached_tile = self.move_toward_tile(next_tile, wall_rects)

        if reached_tile and self.path:
            self.path.pop(0)

    def move_toward_tile(self, tile, wall_rects):
        """
        Moves smoothly toward a tile center.

        Returns True when the fox reaches the tile.
        """
        target_col, target_row = tile

        target_x = target_col * TILE_SIZE + (TILE_SIZE - FOX_COLLISION_SIZE) // 2
        target_y = target_row * TILE_SIZE + (TILE_SIZE - FOX_COLLISION_SIZE) // 2

        dx = target_x - self.x
        dy = target_y - self.y

        distance = math.hypot(dx, dy)

        if distance <= self.ai_speed:
            self.move(dx, dy, wall_rects)
            return True

        if distance == 0:
            return True

        move_x = (dx / distance) * self.ai_speed
        move_y = (dy / distance) * self.ai_speed

        self.move(move_x, move_y, wall_rects)
        return False

    # -----------------------------
    # BFS pathfinding
    # -----------------------------

    def find_path_between(
        self,
        start_tile,
        target_tile,
        maze_layout,
        portal_rect=None,
        avoid_portal_guard=False,
        extra_buffer_tiles=0,
    ):
        """Finds a BFS path from start_tile to target_tile."""
        if start_tile is None or target_tile is None:
            return []

        if not self.is_walkable_tile(
            start_tile,
            maze_layout,
            portal_rect=portal_rect,
            avoid_portal_guard=avoid_portal_guard,
            extra_buffer_tiles=extra_buffer_tiles,
        ):
            start_tile = self.find_nearby_walkable_tile(
                start_tile,
                maze_layout,
                portal_rect=portal_rect,
                avoid_portal_guard=avoid_portal_guard,
                extra_buffer_tiles=extra_buffer_tiles,
            )

        if not self.is_walkable_tile(
            target_tile,
            maze_layout,
            portal_rect=portal_rect,
            avoid_portal_guard=avoid_portal_guard,
            extra_buffer_tiles=extra_buffer_tiles,
        ):
            target_tile = self.find_nearby_walkable_tile(
                target_tile,
                maze_layout,
                portal_rect=portal_rect,
                avoid_portal_guard=avoid_portal_guard,
                extra_buffer_tiles=extra_buffer_tiles,
            )

        if start_tile is None or target_tile is None:
            return []

        frontier = deque()
        frontier.append(start_tile)

        came_from = {start_tile: None}

        while frontier:
            current_tile = frontier.popleft()

            if current_tile == target_tile:
                return self.reconstruct_path(came_from, current_tile)

            for neighbor in self.get_walkable_neighbors(
                current_tile,
                maze_layout,
                portal_rect=portal_rect,
                avoid_portal_guard=avoid_portal_guard,
                extra_buffer_tiles=extra_buffer_tiles,
            ):
                if neighbor in came_from:
                    continue

                came_from[neighbor] = current_tile
                frontier.append(neighbor)

        return []

    def get_walkable_neighbors(
        self,
        tile,
        maze_layout,
        portal_rect=None,
        avoid_portal_guard=False,
        extra_buffer_tiles=0,
    ):
        """Returns walkable neighbor tiles for BFS."""
        col, row = tile

        candidates = [
            (col + 1, row),
            (col - 1, row),
            (col, row + 1),
            (col, row - 1),
        ]

        neighbors = []

        for candidate in candidates:
            if self.is_walkable_tile(
                candidate,
                maze_layout,
                portal_rect=portal_rect,
                avoid_portal_guard=avoid_portal_guard,
                extra_buffer_tiles=extra_buffer_tiles,
            ):
                neighbors.append(candidate)

        return neighbors

    def reconstruct_path(self, came_from, current_tile):
        """Reconstructs a BFS path from the came_from dictionary."""
        path = []

        while current_tile is not None:
            path.append(current_tile)
            current_tile = came_from[current_tile]

        path.reverse()
        return path

    # -----------------------------
    # Tile helpers
    # -----------------------------

    def get_tile_position(self, position):
        """Converts a pixel position to a maze tile coordinate."""
        x, y = position

        col = int(x // TILE_SIZE)
        row = int(y // TILE_SIZE)

        return (col, row)

    def is_inside_maze(self, tile, maze_layout):
        """Returns True if a tile is inside the maze grid."""
        col, row = tile

        if row < 0 or row >= len(maze_layout):
            return False

        if col < 0 or col >= len(maze_layout[row]):
            return False

        return True

    def is_walkable_tile(
        self,
        tile,
        maze_layout,
        portal_rect=None,
        avoid_portal_guard=False,
        extra_buffer_tiles=0,
    ):
        """Returns True if a tile can be used by the fox pathfinding system."""
        if tile is None:
            return False

        if not self.is_inside_maze(tile, maze_layout):
            return False

        col, row = tile

        if maze_layout[row][col] != "0":
            return False

        if avoid_portal_guard and portal_rect is not None:
            return self.is_tile_outside_portal_guard(
                tile,
                portal_rect,
                extra_buffer_tiles=extra_buffer_tiles,
            )

        return True

    def find_nearby_walkable_tile(
        self,
        tile,
        maze_layout,
        portal_rect=None,
        avoid_portal_guard=False,
        extra_buffer_tiles=0,
    ):
        """
        Finds the closest walkable tile near a given tile.

        This prevents AI crashes or stalls when a target lands slightly inside a
        wall or blocked tile.
        """
        if tile is None:
            return None

        if self.is_walkable_tile(
            tile,
            maze_layout,
            portal_rect=portal_rect,
            avoid_portal_guard=avoid_portal_guard,
            extra_buffer_tiles=extra_buffer_tiles,
        ):
            return tile

        start_col, start_row = tile

        for radius in range(1, 6):
            candidates = []

            for row_offset in range(-radius, radius + 1):
                for col_offset in range(-radius, radius + 1):
                    candidate = (
                        start_col + col_offset,
                        start_row + row_offset,
                    )

                    if self.is_walkable_tile(
                        candidate,
                        maze_layout,
                        portal_rect=portal_rect,
                        avoid_portal_guard=avoid_portal_guard,
                        extra_buffer_tiles=extra_buffer_tiles,
                    ):
                        candidates.append(candidate)

            if candidates:
                candidates.sort(
                    key=lambda candidate: self.tile_manhattan_distance(
                        tile,
                        candidate,
                    )
                )
                return candidates[0]

        return None

    def find_nearby_portal_safe_tile(
        self,
        tile,
        portal_rect,
        maze_layout,
        extra_buffer_tiles=1,
        max_radius=8,
    ):
        """Finds a nearby walkable tile outside the active portal guard."""
        if tile is None:
            return None

        if (
            self.is_walkable_tile(tile, maze_layout)
            and self.is_tile_outside_portal_guard(
                tile,
                portal_rect,
                extra_buffer_tiles=extra_buffer_tiles,
            )
        ):
            return tile

        start_col, start_row = tile

        for radius in range(1, max_radius + 1):
            candidates = []

            for row_offset in range(-radius, radius + 1):
                for col_offset in range(-radius, radius + 1):
                    candidate = (
                        start_col + col_offset,
                        start_row + row_offset,
                    )

                    if not self.is_walkable_tile(candidate, maze_layout):
                        continue

                    if not self.is_tile_outside_portal_guard(
                        candidate,
                        portal_rect,
                        extra_buffer_tiles=extra_buffer_tiles,
                    ):
                        continue

                    candidates.append(candidate)

            if candidates:
                candidates.sort(
                    key=lambda candidate: self.tile_manhattan_distance(
                        tile,
                        candidate,
                    )
                )
                return candidates[0]

        return None

    def get_random_walkable_tile(self, maze_layout):
        """Returns a random open tile from the maze."""
        walkable_tiles = []

        for row_index, row in enumerate(maze_layout):
            for col_index, tile in enumerate(row):
                if tile == "0":
                    walkable_tiles.append((col_index, row_index))

        if not walkable_tiles:
            return self.get_tile_position(self.rect.center)

        return random.choice(walkable_tiles)

    def tile_manhattan_distance(self, tile_a, tile_b):
        """Returns Manhattan distance between two tile coordinates."""
        col_a, row_a = tile_a
        col_b, row_b = tile_b

        return abs(col_a - col_b) + abs(row_a - row_b)

    def is_tile_outside_portal_guard(self, tile, portal_rect, extra_buffer_tiles=2):
        """
        Returns True if a tile is safely outside the portal anti-camping zone.

        The extra buffer prevents the fox from choosing a target directly on the
        edge of the guard radius, which can cause jittering or freezing.
        """
        if portal_rect is None:
            return True

        tile_col, tile_row = tile

        tile_center_x = tile_col * TILE_SIZE + TILE_SIZE // 2
        tile_center_y = tile_row * TILE_SIZE + TILE_SIZE // 2

        portal_x, portal_y = portal_rect.center

        distance = math.hypot(
            tile_center_x - portal_x,
            tile_center_y - portal_y,
        )

        return distance >= PORTAL_GUARD_RADIUS + (extra_buffer_tiles * TILE_SIZE)

    # -----------------------------
    # Collision movement
    # -----------------------------

    def move(self, dx, dy, wall_rects):
        """Moves the fox while resolving wall collisions and corner assist."""
        if dx != 0:
            self.move_axis(dx, 0, wall_rects)

        if dy != 0:
            self.move_axis(0, dy, wall_rects)

    def move_axis(self, dx, dy, wall_rects):
        """Moves on one axis and resolves collision."""
        original_x = self.x
        original_y = self.y

        self.x += dx
        self.y += dy
        self.sync_rect_to_position()

        if not self.is_colliding(wall_rects):
            return

        self.x = original_x
        self.y = original_y
        self.sync_rect_to_position()

        self.try_corner_assist(dx, dy, wall_rects)

    def try_corner_assist(self, dx, dy, wall_rects):
        """Attempts small sliding movements around corners."""
        if dx != 0:
            self.try_horizontal_corner_assist(dx, wall_rects)

        elif dy != 0:
            self.try_vertical_corner_assist(dy, wall_rects)

    def try_horizontal_corner_assist(self, dx, wall_rects):
        """Tries to slide up or down while moving horizontally."""
        for offset in self.get_assist_offsets():
            original_x = self.x
            original_y = self.y

            self.y += offset
            self.sync_rect_to_position()

            if self.is_colliding(wall_rects):
                self.x = original_x
                self.y = original_y
                self.sync_rect_to_position()
                continue

            self.x += dx
            self.sync_rect_to_position()

            if not self.is_colliding(wall_rects):
                return

            self.x = original_x
            self.y = original_y
            self.sync_rect_to_position()

    def try_vertical_corner_assist(self, dy, wall_rects):
        """Tries to slide left or right while moving vertically."""
        for offset in self.get_assist_offsets():
            original_x = self.x
            original_y = self.y

            self.x += offset
            self.sync_rect_to_position()

            if self.is_colliding(wall_rects):
                self.x = original_x
                self.y = original_y
                self.sync_rect_to_position()
                continue

            self.y += dy
            self.sync_rect_to_position()

            if not self.is_colliding(wall_rects):
                return

            self.x = original_x
            self.y = original_y
            self.sync_rect_to_position()

    def get_assist_offsets(self):
        """Returns corner-assist offset values."""
        offsets = []

        for distance in range(1, self.CORNER_ASSIST_DISTANCE + 1):
            offsets.append(distance)
            offsets.append(-distance)

        return offsets

    def is_colliding(self, wall_rects):
        """Returns True if the fox collision rect touches any wall."""
        for wall_rect in wall_rects:
            if self.rect.colliderect(wall_rect):
                return True

        return False

    # -----------------------------
    # Drawing
    # -----------------------------

    def draw(self, screen):
        """Draws the fox sprite or fallback shape."""
        if self.image:
            screen.blit(self.image, self.get_draw_rect())
        else:
            self.draw_fallback(screen)

    def draw_fallback(self, screen):
        """Draws a fallback fox if the sprite is missing."""
        pygame.draw.ellipse(
            screen,
            (190, 95, 45),
            self.rect,
        )

        pygame.draw.ellipse(
            screen,
            (255, 190, 120),
            self.rect.inflate(-8, -8),
        )

    def scale_image_to_height(self, image, target_height):
        """Scales an image by height while preserving proportions."""
        if image is None:
            return None

        original_width = image.get_width()
        original_height = image.get_height()

        if original_height == 0:
            return image

        scale_ratio = target_height / original_height
        new_width = int(original_width * scale_ratio)

        return pygame.transform.smoothscale(image, (new_width, target_height))
