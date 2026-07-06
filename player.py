"""
player.py

Player controller for The Shifting Grove.

This module defines the human explorer used in the main maze. The player uses a
small collision rectangle for responsive movement while drawing a larger sprite
centered over that collision box for a more polished visual appearance.

Responsibilities:
- read WASD movement input
- move through the maze while respecting wall collisions
- clamp the player inside the screen bounds
- apply corner assist so narrow maze turns feel less sticky
- draw either the player sprite or a simple fallback rectangle
"""

import pygame

from asset_loader import load_image
from settings import (
    PLAYER_COLLISION_SIZE,
    PLAYER_COLOR,
    PLAYER_IMAGE,
    PLAYER_SPEED,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)


class Player:
    """Human explorer controlled with WASD in the main maze."""

    # Number of pixels the game may gently nudge the player around corners.
    CORNER_ASSIST_DISTANCE = 8

    # Visual sprite height. The collision box stays smaller for smoother movement.
    SPRITE_DRAW_HEIGHT = 70

    def __init__(self, x, y):
        self.rect = pygame.Rect(
            x,
            y,
            PLAYER_COLLISION_SIZE,
            PLAYER_COLLISION_SIZE,
        )
        self.speed = PLAYER_SPEED

        raw_player_image = load_image(PLAYER_IMAGE, use_alpha=True)
        self.image = self.scale_image_to_height(
            raw_player_image,
            self.SPRITE_DRAW_HEIGHT,
        )

    def update(self, wall_rects):
        """Updates the player each frame."""
        self.handle_input(wall_rects)

    def handle_input(self, wall_rects):
        """Reads WASD input and moves the player."""
        keys = pygame.key.get_pressed()

        dx = 0
        dy = 0

        if keys[pygame.K_w]:
            dy -= self.speed
        if keys[pygame.K_s]:
            dy += self.speed
        if keys[pygame.K_a]:
            dx -= self.speed
        if keys[pygame.K_d]:
            dx += self.speed

        self.move(dx, dy, wall_rects)

    def move(self, dx, dy, wall_rects):
        """
        Moves the player while preventing wall clipping.

        Horizontal and vertical movement are handled separately. This gives
        smoother collision response and allows corner assist to help the player
        slide through tight maze openings.
        """
        if dx == 0 and dy == 0:
            return

        self.move_axis(dx, 0, wall_rects)
        self.move_axis(0, dy, wall_rects)

        self.rect.clamp_ip(pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))

    def move_axis(self, dx, dy, wall_rects):
        """
        Moves on one axis and resolves wall collisions.

        If movement is blocked, corner assist tries a small perpendicular nudge
        before rejecting the movement completely.
        """
        if dx == 0 and dy == 0:
            return

        self.rect.x += dx
        self.rect.y += dy

        if not self.is_colliding(wall_rects):
            return

        # Undo the blocked movement before trying assisted movement.
        self.rect.x -= dx
        self.rect.y -= dy

        self.try_corner_assist(dx, dy, wall_rects)

    def try_corner_assist(self, dx, dy, wall_rects):
        """
        Attempts a small perpendicular adjustment when movement is blocked.

        Returns:
            True if a valid assisted movement was found, otherwise False.
        """
        if dx != 0:
            return self.try_horizontal_corner_assist(dx, wall_rects)

        if dy != 0:
            return self.try_vertical_corner_assist(dy, wall_rects)

        return False

    def try_horizontal_corner_assist(self, dx, wall_rects):
        """Tries to help left/right movement by nudging vertically."""
        for offset in self.get_assist_offsets():
            original_position = self.rect.copy()
            self.rect.y += offset

            if not self.is_colliding(wall_rects):
                self.rect.x += dx

                if not self.is_colliding(wall_rects):
                    return True

            self.rect = original_position

        return False

    def try_vertical_corner_assist(self, dy, wall_rects):
        """Tries to help up/down movement by nudging horizontally."""
        for offset in self.get_assist_offsets():
            original_position = self.rect.copy()
            self.rect.x += offset

            if not self.is_colliding(wall_rects):
                self.rect.y += dy

                if not self.is_colliding(wall_rects):
                    return True

            self.rect = original_position

        return False

    def get_assist_offsets(self):
        """
        Returns small nudge distances ordered from smallest to largest.

        Alternating positive and negative offsets keeps corner assist from
        pulling the player consistently in one direction.
        """
        offsets = []

        for distance in range(1, self.CORNER_ASSIST_DISTANCE + 1):
            offsets.append(distance)
            offsets.append(-distance)

        return offsets

    def get_colliding_wall(self, wall_rects):
        """Returns the first wall the player is colliding with, or None."""
        for wall in wall_rects:
            if self.rect.colliderect(wall):
                return wall

        return None

    def is_colliding(self, wall_rects):
        """Returns True if the player is colliding with any wall."""
        return self.get_colliding_wall(wall_rects) is not None

    def draw(self, screen):
        """
        Draws the player sprite or fallback rectangle.

        The sprite is centered over the smaller collision rectangle so the
        explorer appears larger without making movement feel bulky.
        """
        if self.image:
            sprite_rect = self.image.get_rect(center=self.rect.center)
            screen.blit(self.image, sprite_rect)
            return

        pygame.draw.rect(screen, PLAYER_COLOR, self.rect)

    def scale_image_to_height(self, image, target_height):
        """Scales an image by height while preserving its aspect ratio."""
        if image is None:
            return None

        original_width = image.get_width()
        original_height = image.get_height()

        if original_height == 0:
            return image

        scale_ratio = target_height / original_height
        new_width = int(original_width * scale_ratio)

        return pygame.transform.smoothscale(image, (new_width, target_height))
