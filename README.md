# The Shifting Grove

**The Shifting Grove** is a Python/Pygame fantasy maze game where the player explores an enchanted forest, collects Grove Shards, avoids a fox guardian, and completes mini-games to earn rewards that affect the main maze.

This project was developed as a software portfolio piece to demonstrate object-oriented programming, procedural generation, AI pathfinding, collision handling, finite state machines, modular project organization, and game-state integration across multiple mini-games.

---

## Demo

A gameplay demo video and visual project overview will be available on my portfolio website:

https://anshiamy.github.io/

This repository focuses on the source code, project structure, technical implementation, and instructions for running the game locally.

---

## Gameplay Overview

The player controls an explorer trapped inside an enchanted forest maze. To escape, the player must collect **three Grove Shards**, activate the portal, and reach it before the Grove Shift Meter fills.

A fox guardian creates pressure throughout the maze. In single-player mode, the fox is controlled by AI. In local multiplayer mode, a second player can control the fox using the arrow keys.

Mini-game triggers appear inside the maze during gameplay. Completing a mini-game allows the winning side to choose a reward that affects the main maze state.

---

## Features

- Procedurally generated maze layout
- Player-controlled explorer with collision handling
- Fox guardian with AI pathfinding
- Single-player and local multiplayer modes
- Collectible Grove Shards
- Locked and active portal states
- Grove Shift Meter pressure system
- Portal anti-camping behavior
- Three integrated mini-games:
  - **The Sigil’s Echo**
  - **Starlight Crossing**
  - **Canopy Cascade**
- Reward system that affects the main game state
- Custom UI/HUD with lives, shard count, timers, and status effects
- Animated transition screens and visual feedback
- Asset fallback handling for missing images

---

## Mini-Games

### The Sigil’s Echo

A memory-pattern challenge where the explorer and fox compete by repeating directional sequences. The player must match the glowing pattern before time runs out.

### Starlight Crossing

A puzzle-based mini-game where the explorer and fox solve separate starlight circuit boards. The goal is to connect paths efficiently before the opponent finishes or the timer expires.

### Canopy Cascade

A falling-object collection mini-game where the explorer and fox compete to catch helpful items while avoiding penalties.

---

## Rewards

Mini-games return rewards that modify the main maze state.

### Explorer Rewards

| Reward | Effect |
|---|---|
| Grove Calm | Reduces the Grove Shift Meter |
| Lantern Shield | Blocks the fox’s next catch |
| Fox Banish | Temporarily pauses the fox |

### Fox Rewards

| Reward | Effect |
|---|---|
| Mischief Surge | Increases the Grove Shift Meter |
| Shadow Rush | Temporarily increases fox speed |
| Portal Flicker | Temporarily delays or destabilizes the portal |

---

## Controls

### Main Maze

| Action | Control |
|---|---|
| Move explorer | W A S D |
| Move fox in local multiplayer | Arrow Keys |
| Return/back on menu screens | ESC |
| Restart after win/loss | R |

### Mini-Games

Each mini-game explains its controls in-game.

Common controls include:

| Action | Control |
|---|---|
| Continue/start mini-game | SPACE |
| Select reward | 1, 2, or 3 |
| Explorer movement/input | W A S D |
| Fox movement/input in local multiplayer | Arrow Keys |

---

## Technical Highlights

This project demonstrates several software development concepts:

- **Object-oriented programming:** separate classes for the player, fox, maze, shards, UI systems, and mini-games
- **Finite state machines:** main game states and mini-game phases are controlled through explicit state transitions
- **Procedural generation:** maze layouts are generated dynamically using randomized depth-first search
- **Pathfinding and AI behavior:** the fox uses AI logic to patrol, chase, search, intercept, recover, and pressure objectives
- **Collision handling:** player, fox, walls, shards, portal, and mini-game triggers use rectangle-based collision checks
- **Mini-game integration:** each mini-game runs independently, returns a selected reward, and passes that result back to the main maze
- **Shared reward system:** rewards from different mini-games affect the same main game state
- **Modular architecture:** separate files organize gameplay logic, UI, configuration, assets, and mini-games
- **Asset fallback handling:** missing assets are handled safely where possible so the game can continue running

---

## Project Structure

```text
The-Shifting-Grove/
├── assets/
│   ├── images/
│   └── fonts/
├── main.py
├── settings.py
├── game.py
├── asset_loader.py
├── player.py
├── fox.py
├── maze.py
├── shard.py
├── ui.py
├── sigils_echo.py
├── starlight_crossing.py
├── cascading_canopy.py
├── requirements.txt
├── README.md
└── .gitignore
```

### Main Files

| File | Purpose |
|---|---|
| `main.py` | Entry point for running the game |
| `game.py` | Main game coordinator and state manager |
| `settings.py` | Shared constants, paths, and configuration values |
| `asset_loader.py` | Shared image-loading helper |
| `player.py` | Explorer movement, collision, and drawing |
| `fox.py` | Fox movement, AI behavior, and pathfinding |
| `maze.py` | Procedural maze generation and portal placement |
| `shard.py` | Grove Shard collectible logic |
| `ui.py` | HUD, visual feedback, transitions, and buttons |
| `sigils_echo.py` | The Sigil’s Echo mini-game |
| `starlight_crossing.py` | Starlight Crossing mini-game |
| `cascading_canopy.py` | Canopy Cascade mini-game |

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/AnshiaMY/The-Shifting-Grove.git
cd The-Shifting-Grove
```

### 2. Create a virtual environment

For macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

For Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the game

```bash
python main.py
```

---

## Requirements

```text
pygame
```

The project was developed using Python and Pygame.

---

## Known Limitations

- The game is designed for a fixed `1024x768` window.
- Local multiplayer uses one keyboard.
- The game is currently a desktop Pygame project, not a browser-based game.
- Gameplay balance may be adjusted with further playtesting.

---

## Future Improvements

Potential improvements include:

- Add difficulty settings
- Add controller support
- Add more sound effects and background music
- Add more maze events
- Add additional mini-games
- Add a pause menu
- Add persistent high scores or completion stats
- Package the game as an executable

---

## Asset Credits

- **Font:** Cinzel Decorative from Google Fonts.
- **Visual assets:** Game artwork, backgrounds, icons, buttons, character sprites, mini-game screens, and UI visuals were generated with AI assistance through ChatGPT and then selected, edited, organized, and integrated into the final Pygame project.
- **Code:** All gameplay systems, game logic, state management, mini-game integration, and project organization were coded and implemented by Anshia Muhammad Yaqoob as part of this portfolio project.

---

## Author

Created by **Anshia Muhammad Yaqoob** as a Python/Pygame software portfolio project.

Portfolio: https://anshiamy.github.io/

This project was developed to demonstrate programming, game logic, procedural generation, AI behavior, UI design, and multi-file software organization for engineering/software co-op applications.
