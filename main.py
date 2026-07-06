"""
main.py

Entry point for the Maze Runner game.

This file creates a Game object and starts the main game loop. Keeping the entry
point small makes the project easier to read and keeps game logic inside game.py.
"""

from game import Game


if __name__ == "__main__":
    game = Game()
    game.run()