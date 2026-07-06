"""
shard.py

Defines the GroveShard class.

Grove Shards are magical collectible objects that the human player must collect
before the portal can open. Each shard can use an image asset, but it also has
a fallback glowing crystal drawing so the game still works if the image is
missing.
"""

import math
import pygame

from asset_loader import load_image
from settings import (
    GROVE_SHARD_IMAGE,
    SHARD_COLLISION_SIZE,
    SHARD_SPRITE_SIZE,
)


class GroveShard:
    """Represents one collectible Grove Shard in the maze."""

    def __init__(self, center_x, center_y):
        self.rect = pygame.Rect(
            0,
            0,
            SHARD_COLLISION_SIZE,
            SHARD_COLLISION_SIZE,
        )
        self.rect.center = (center_x, center_y)

        self.image = load_image(
            GROVE_SHARD_IMAGE,
            (SHARD_SPRITE_SIZE, SHARD_SPRITE_SIZE),
            use_alpha=True,
        )

        self.collected = False
        self.animation_timer = 0

    def update(self):
        """Updates the shard animation timer."""
        self.animation_timer += 1

    def draw(self, screen):
        """Draws the shard if it has not been collected."""
        if self.collected:
            return

        if self.image:
            self.draw_image(screen)
        else:
            self.draw_fallback_crystal(screen)

    def draw_image(self, screen):
        """Draws the shard image with a subtle floating motion."""
        float_offset = math.sin(self.animation_timer * 0.08) * 3

        image_rect = self.image.get_rect(
            center=(self.rect.centerx, self.rect.centery + float_offset)
        )

        screen.blit(self.image, image_rect)

    def draw_fallback_crystal(self, screen):
        """
        Draws a glowing fallback shard.

        This keeps the game playable and visually clear even before a custom
        shard image is added to the assets folder.
        """
        float_offset = math.sin(self.animation_timer * 0.08) * 3
        center_x = self.rect.centerx
        center_y = self.rect.centery + float_offset

        glow_radius = 24 + int(math.sin(self.animation_timer * 0.06) * 3)

        glow_surface = pygame.Surface((70, 70), pygame.SRCALPHA)
        pygame.draw.circle(
            glow_surface,
            (120, 220, 255, 65),
            (35, 35),
            glow_radius,
        )
        pygame.draw.circle(
            glow_surface,
            (210, 245, 255, 45),
            (35, 35),
            glow_radius // 2,
        )

        screen.blit(glow_surface, (center_x - 35, center_y - 35))

        crystal_points = [
            (center_x, center_y - 20),
            (center_x + 13, center_y - 4),
            (center_x + 7, center_y + 18),
            (center_x, center_y + 24),
            (center_x - 7, center_y + 18),
            (center_x - 13, center_y - 4),
        ]

        pygame.draw.polygon(screen, (150, 230, 255), crystal_points)
        pygame.draw.polygon(screen, (235, 255, 255), crystal_points, 2)

        highlight_points = [
            (center_x, center_y - 15),
            (center_x + 5, center_y - 3),
            (center_x, center_y + 13),
            (center_x - 4, center_y - 3),
        ]

        pygame.draw.polygon(screen, (245, 255, 255), highlight_points)