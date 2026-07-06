"""
asset_loader.py

Provides helper functions for loading and scaling image assets used in the game.

If an image file is missing or cannot be loaded, the function returns None so
the game can fall back to simple shapes instead of crashing.
"""

import pygame


def load_image(path, size=None, use_alpha=True):
    """
    Loads an image from the given file path and optionally resizes it.

    Args:
        path: Path object or string pointing to the image file.
        size: Optional tuple for resizing the image, such as (32, 32).
        use_alpha: Whether to preserve transparency in PNG images.

    Returns:
        A Pygame Surface if loading succeeds, or None if loading fails.
    """

    # Do not crash the game if the image file does not exist.
    if not path.exists():
        print(f"Warning: Missing image asset: {path}")
        return None

    try:
        image = pygame.image.load(str(path))

        # convert_alpha keeps transparent backgrounds for sprites like the
        # player and door. convert is better for full backgrounds.
        if use_alpha:
            image = image.convert_alpha()
        else:
            image = image.convert()

        if size:
            image = pygame.transform.scale(image, size)

        return image

    except pygame.error as error:
        print(f"Warning: Could not load image {path}. Error: {error}")
        return None