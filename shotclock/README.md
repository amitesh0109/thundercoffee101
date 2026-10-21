# 🏀 Shot Clock

A terminal basketball arcade game that plays while Claude Code is thinking.

## Quick Start

### Standalone Mode

```bash
python3 shotclock.py
```

### With Claude Code (requires tmux)

```bash
python3 install_hooks.py
```

This installs hooks that automatically open the game in a tmux split pane after Claude has been thinking for 5+ seconds.

## Controls

| Key | Action |
|-----|--------|
| ←→ | Move your aim left/right (the dotted arc shows where the shot lands) |
| ↑↓ | Adjust distance (unlocks at 100 pts) |
| SPACE | Shoot |
| P | Pause / resume |
| R | Restart game |
| Q | Quit |

## Gameplay

- **Goal:** Make as many baskets as possible before losing 5 lives
- **Scoring:** 2 points per basket
- **Lives:** Miss 5 shots = game over

### Progression

| Score | What Changes |
|-------|-------------|
| **50** | 🛡️ Defender appears (blocks shots) |
| **75** | 🚀 Hoop moves faster |
| **100** | 📐 Hoop moves in 3D (use ↑↓ to control distance) |
| **150** | 💣 Bombs appear randomly - aim for trash can! |
| **Every 25 after 100** | Speed increases |

### Bombs (150+)

- 25% chance each shot becomes a bomb
- A trash can spawns on the left side
- **Must hit the trash can** (not the hoop!)
- Bomb explodes if it crosses the trash can line outside the can
- **Explosion = -2 lives** (ouch!)

## Requirements

- Python 3.6+
- Standard library only (uses `curses`)
- tmux (optional, for Claude Code integration)
- Terminal size: minimum 40×15

## File Structure

```
shotclock/
├── shotclock.py        # Main game
├── install_hooks.py    # Hook installer for Claude Code
├── requirements.txt    # Dependencies (none!)
└── README.md          # This file
```

## Configuration

### Disable the game

```bash
export SHOTCLOCK=off
```

### Uninstall hooks

```bash
python3 install_hooks.py uninstall
```

## Technical Details

- **Physics:** Parabolic trajectory with gravity (-2.0)
- **Frame rate:** 30 FPS
- **Flight time:** 1.2 seconds per shot
- **Collision:** 2-char hitbox for defender
- **Persistence:** High scores saved to `~/.shotclock/scores.json`

## Known Limitations

- Hook integration is conceptual - event names need verification against real Claude Code API
- Terminal must support Unicode characters (emojis are optional with fallbacks)
- Requires color support for best experience (works without it though)

## Roadmap

**v0.2:**
- Sound effects (terminal beep)
- Enhanced stats screen
- Session replay

**v1.0:**
- Port to Go/Rust for single binary
- Team leaderboard
- Daily challenges
- Custom themes

## Credits

Built as a companion for [Claude Code](https://github.com/anthropics/claude-code).

Inspired by Chrome's offline dinosaur game.
