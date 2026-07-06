"""
maze.py

Procedural maze generation and rendering for The Shifting Grove.

The Maze class builds a randomized tile-based maze for the main game. It uses a
randomized depth-first search to carve a connected base maze, opens additional
walls to create alternate routes, then places the portal on a far reachable tile.
Before finalizing the portal location, the generator checks that the player has
multiple possible paths from the starting area.

This module owns:
- maze layout generation
- loop/alternate-route creation
- portal placement and portal clearance
- wall and portal drawing
- collision rectangles for walls

The layout uses simple symbols so other modules can read it easily:
- "1" = wall tile
- "0" = open path tile
- "D" = door/portal tile
"""

import random
from collections import deque

import pygame

from asset_loader import load_image
from settings import (
    DOOR_COLOR,
    DOOR_IMAGE,
    DOOR_LOCKED_IMAGE,
    DOOR_SPRITE_SIZE,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TILE_SIZE,
    WALL_COLOR,
    WALL_IMAGE,
)


class Maze:
    """Generates, stores, draws, and exposes collision data for the maze."""

    EXTRA_LOOP_COUNT = 45
    MIN_PATHS_TO_DOOR = 3
    MAX_GENERATION_ATTEMPTS = 80
    PATH_SEARCH_LIMIT = 20000

    def __init__(self):
        self.cols = SCREEN_WIDTH // TILE_SIZE
        self.rows = SCREEN_HEIGHT // TILE_SIZE

        self.start_col = 1
        self.start_row = 1

        self.layout = self.generate_maze()

        self.wall_image = load_image(
            WALL_IMAGE,
            (TILE_SIZE, TILE_SIZE),
        )

        raw_door_image = load_image(DOOR_IMAGE, use_alpha=True)
        self.door_image = self.scale_image_to_height(raw_door_image, DOOR_SPRITE_SIZE)

        raw_locked_door_image = load_image(DOOR_LOCKED_IMAGE, use_alpha=True)
        self.locked_door_image = self.scale_image_to_height(
            raw_locked_door_image,
            DOOR_SPRITE_SIZE,
        )

        self.door_rect = self.get_door_rect()

    # -----------------------------
    # Maze generation
    # -----------------------------

    def generate_maze(self):
        """
        Generates a randomized maze with alternate routes to the portal.

        Several generation attempts are allowed. Each attempt creates a connected
        maze, adds loops, and tries to place the portal on a far tile with enough
        distinct paths from the player start. If no ideal tile is found, the maze
        falls back to the farthest reachable open tile so gameplay can continue.
        """

        for _ in range(self.MAX_GENERATION_ATTEMPTS):
            grid = self.create_wall_grid()
            self.carve_base_maze(grid)
            self.add_loops(grid)

            door_tile = self.find_valid_door_tile(grid)

            if door_tile:
                door_col, door_row = door_tile

                self.clear_portal_area(grid, door_col, door_row)
                grid[door_row][door_col] = "D"

                return self.convert_grid_to_layout(grid)

        # Fallback: keep the game playable even if the ideal portal tile is not found.
        grid = self.create_wall_grid()
        self.carve_base_maze(grid)
        self.add_loops(grid)

        door_col, door_row = self.find_farthest_open_tile(grid)

        self.clear_portal_area(grid, door_col, door_row)
        grid[door_row][door_col] = "D"

        return self.convert_grid_to_layout(grid)

    def create_wall_grid(self):
        """Creates a maze-sized grid initially filled with wall tiles."""
        return [["1" for _ in range(self.cols)] for _ in range(self.rows)]

    def carve_base_maze(self, grid):
        """
        Carves a solvable base maze using randomized depth-first search.

        This creates a connected maze where every carved path can be reached
        from the player's starting tile.
        """

        grid[self.start_row][self.start_col] = "0"
        stack = [(self.start_col, self.start_row)]

        directions = [
            (0, -2),
            (0, 2),
            (-2, 0),
            (2, 0),
        ]

        while stack:
            current_col, current_row = stack[-1]

            shuffled_directions = directions[:]
            random.shuffle(shuffled_directions)

            carved_new_path = False

            for col_change, row_change in shuffled_directions:
                next_col = current_col + col_change
                next_row = current_row + row_change

                if self.is_inside_maze(next_col, next_row):
                    if grid[next_row][next_col] == "1":
                        wall_col = current_col + col_change // 2
                        wall_row = current_row + row_change // 2

                        grid[wall_row][wall_col] = "0"
                        grid[next_row][next_col] = "0"

                        stack.append((next_col, next_row))
                        carved_new_path = True
                        break

            if not carved_new_path:
                stack.pop()

    def add_loops(self, grid):
        """
        Removes selected walls to create alternate routes through the maze.

        A pure depth-first-search maze usually has only one route between two
        points. Removing some walls creates loops, shortcuts, and multiple route
        options, which makes the maze better for gameplay.
        """

        candidates = []

        for row in range(1, self.rows - 1):
            for col in range(1, self.cols - 1):
                if grid[row][col] == "1":
                    horizontal_connection = (
                        grid[row][col - 1] == "0"
                        and grid[row][col + 1] == "0"
                    )

                    vertical_connection = (
                        grid[row - 1][col] == "0"
                        and grid[row + 1][col] == "0"
                    )

                    if horizontal_connection or vertical_connection:
                        candidates.append((col, row))

        random.shuffle(candidates)

        for col, row in candidates[: self.EXTRA_LOOP_COUNT]:
            grid[row][col] = "0"

    def clear_portal_area(self, grid, door_col, door_row):
        """
        Clears a small open area around the portal.

        The portal sprite is larger than one tile, so this gives it visual
        breathing room and prevents it from looking like it is sitting on top
        of wall blocks.
        """

        for row in range(door_row - 1, door_row + 2):
            for col in range(door_col - 1, door_col + 2):
                if self.is_inside_maze(col, row):
                    grid[row][col] = "0"

    # -----------------------------
    # Door placement helpers
    # -----------------------------

    def find_valid_door_tile(self, grid):
        """
        Finds a far portal tile with enough valid paths from the start.

        Candidate tiles are checked from farthest to closest so the portal still
        appears deep in the maze instead of too close to the player.
        """

        candidates = self.get_open_tiles_by_distance(grid)

        for col, row, _distance in candidates:
            distance_from_start = abs(col - self.start_col) + abs(row - self.start_row)

            if distance_from_start < 10:
                continue

            path_count = self.count_paths_to_tile(
                grid,
                target_col=col,
                target_row=row,
                path_limit=self.MIN_PATHS_TO_DOOR,
            )

            if path_count >= self.MIN_PATHS_TO_DOOR:
                return col, row

        return None

    def get_open_tiles_by_distance(self, grid):
        """
        Returns open tiles sorted from farthest to closest from the start.

        Breadth-first search is used to measure distance through the maze paths.
        """

        visited = set()
        queue = deque()

        queue.append((self.start_col, self.start_row, 0))
        visited.add((self.start_col, self.start_row))

        open_tiles = []

        while queue:
            col, row, distance = queue.popleft()
            open_tiles.append((col, row, distance))

            for next_col, next_row in self.get_open_neighbors(grid, col, row):
                if (next_col, next_row) not in visited:
                    visited.add((next_col, next_row))
                    queue.append((next_col, next_row, distance + 1))

        open_tiles.sort(key=lambda tile: tile[2], reverse=True)
        return open_tiles

    def count_paths_to_tile(self, grid, target_col, target_row, path_limit):
        """
        Counts distinct simple paths from the start to a target tile.

        The search stops once path_limit paths are found. This verifies that the
        selected portal has multiple routes without needing to count every
        possible path in the maze.
        """

        path_count = 0
        search_steps = 0
        visited = set()

        def dfs(col, row):
            nonlocal path_count, search_steps

            if path_count >= path_limit:
                return

            if search_steps >= self.PATH_SEARCH_LIMIT:
                return

            search_steps += 1

            if col == target_col and row == target_row:
                path_count += 1
                return

            visited.add((col, row))

            for next_col, next_row in self.get_open_neighbors(grid, col, row):
                if (next_col, next_row) not in visited:
                    dfs(next_col, next_row)

            visited.remove((col, row))

        dfs(self.start_col, self.start_row)
        return path_count

    def find_farthest_open_tile(self, grid):
        """
        Finds the farthest reachable open tile from the start.

        This is used as a fallback if the generator cannot find a portal tile
        with the required number of alternate paths after several attempts.
        """

        open_tiles = self.get_open_tiles_by_distance(grid)

        if open_tiles:
            farthest_col, farthest_row, _distance = open_tiles[0]
            return farthest_col, farthest_row

        return self.start_col, self.start_row

    # -----------------------------
    # Grid helpers
    # -----------------------------

    def get_open_neighbors(self, grid, col, row):
        """Returns neighboring tiles that can be traversed."""
        neighbors = []

        directions = [
            (0, -1),
            (0, 1),
            (-1, 0),
            (1, 0),
        ]

        for col_change, row_change in directions:
            next_col = col + col_change
            next_row = row + row_change

            if 0 <= next_col < self.cols and 0 <= next_row < self.rows:
                if grid[next_row][next_col] in ("0", "D"):
                    neighbors.append((next_col, next_row))

        return neighbors

    def is_inside_maze(self, col, row):
        """Checks whether a tile is inside the maze border."""
        return 1 <= col < self.cols - 1 and 1 <= row < self.rows - 1

    def convert_grid_to_layout(self, grid):
        """Converts the 2D grid into the compact string layout format."""
        return ["".join(row) for row in grid]

    # -----------------------------
    # Drawing
    # -----------------------------

    def draw(self, screen, portal_is_active=False):
        """
        Draws the maze walls first, then draws the portal last.

        Drawing the portal last prevents nearby wall tiles from visually covering
        it. The portal image changes depending on whether it is locked or active.

        Args:
            screen: The Pygame surface to draw on.
            portal_is_active: If True, draws the active portal. If False, draws
            the locked/sealed portal.
        """

        door_tile_rect = None

        for row_index, row in enumerate(self.layout):
            for col_index, tile in enumerate(row):
                x = col_index * TILE_SIZE
                y = row_index * TILE_SIZE
                tile_rect = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)

                if tile == "1":
                    self.draw_wall(screen, tile_rect)

                elif tile == "D":
                    door_tile_rect = tile_rect

        if door_tile_rect:
            self.draw_door(screen, door_tile_rect, portal_is_active)

    def draw_wall(self, screen, tile_rect):
        """Draws a wall tile using an image if available, otherwise a rectangle."""
        if self.wall_image:
            screen.blit(self.wall_image, tile_rect)
        else:
            pygame.draw.rect(screen, WALL_COLOR, tile_rect)

    def draw_door(self, screen, tile_rect, portal_is_active=False):
        """
        Draws either the locked or active portal.

        The locked portal appears before all Grove Shards are collected. The
        active portal appears after the player collects all shards.
        """

        if portal_is_active:
            portal_image = self.door_image
        else:
            portal_image = self.locked_door_image

        # If the locked image is missing, fall back to the active image so the
        # game still runs instead of crashing.
        if portal_image is None:
            portal_image = self.door_image

        if portal_image:
            door_sprite_rect = portal_image.get_rect(center=tile_rect.center)
            screen.blit(portal_image, door_sprite_rect)
        else:
            pygame.draw.rect(screen, DOOR_COLOR, tile_rect)

    # -----------------------------
    # Collision helpers
    # -----------------------------

    def get_wall_rects(self):
        """Returns a list of wall rectangles used for player collision detection."""
        wall_rects = []

        for row_index, row in enumerate(self.layout):
            for col_index, tile in enumerate(row):
                if tile == "1":
                    x = col_index * TILE_SIZE
                    y = row_index * TILE_SIZE
                    wall_rects.append(pygame.Rect(x, y, TILE_SIZE, TILE_SIZE))

        return wall_rects

    def get_door_rect(self):
        """Finds the portal tile in the layout and returns it as a rectangle."""
        for row_index, row in enumerate(self.layout):
            for col_index, tile in enumerate(row):
                if tile == "D":
                    x = col_index * TILE_SIZE
                    y = row_index * TILE_SIZE
                    return pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)

        return None

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
