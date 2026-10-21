# 🏀 Shot Clock - Quick Start

## Try it now!

```bash
cd shotclock
python3 shotclock.py
```

Or use the launcher:
```bash
./play.sh
```

## Controls

```
←→  Aim left/right (dotted arc = where it lands)
SPACE  Shoot
P  Pause
R  Restart
Q  Quit
```

(↑↓ unlocks at 100 points for distance control)

## What to expect

1. **Start**: Splash screen for 5 seconds
2. **0-50 pts**: Just you vs. the moving hoop
3. **50 pts**: Defender appears (he blocks shots!)
4. **100 pts**: Hoop moves in 3D, use ↑↓ for distance
5. **150 pts**: Bombs! Aim for the trash can, not the hoop

## Tips

- **Lead your shots** - the hoop keeps moving while the ball is in flight
- The defender has a predictable pattern - time your shots
- Bombs cost 2 lives if they explode, so be careful!
- Streak counter appears after 3 baskets in a row

## Testing

```bash
python3 test_game.py
```

This runs automated tests for:
- Ball trajectory physics
- Collision detection
- Scoring system
- Progression thresholds

## Installation (optional)

To integrate with Claude Code (requires tmux):

```bash
python3 install_hooks.py
```

This sets up hooks so the game auto-opens when Claude is thinking for 5+ seconds.

## Files

- `shotclock.py` - Main game
- `install_hooks.py` - Hook installer
- `test_game.py` - Test suite
- `play.sh` - Quick launcher
- `README.md` - Full documentation

## Troubleshooting

**Terminal too small?**
Resize to at least 40×15 characters.

**Emojis not showing?**
The game has ASCII fallbacks, but emojis make it more fun. Use a modern terminal.

**Game feels laggy?**
30 FPS is the target. Try a different terminal emulator.

## Next Steps

See `README.md` for:
- Full feature documentation
- Claude Code integration details
- Roadmap for v0.2 and v1.0
