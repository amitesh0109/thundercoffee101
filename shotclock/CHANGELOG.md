# Changelog

## v0.1 - Prototype (2026-10-21)

### ✅ Implemented

**Core Gameplay:**
- ✅ Python prototype using curses
- ✅ 30 FPS game loop
- ✅ Ball physics with parabolic trajectory
- ✅ Hoop movement (left-right)
- ✅ Aiming system (←→ for angle, 30°-80°)
- ✅ Shooting (Space bar)
- ✅ One shot at a time (aim next shot while ball in flight)
- ✅ 2 points per basket
- ✅ 5 lives system
- ✅ Game over at 5 misses
- ✅ Auto-restart after 3 seconds

**Progression:**
- ✅ Defender at 50 pts with 2-char hitbox
- ✅ Hoop speed increase at 75 pts
- ✅ 3D hoop movement at 100 pts (forward/backward)
- ✅ Distance control unlocks at 100 pts (↑↓ keys, 10 steps)
- ✅ Speed increases every 25 pts after 100
- ✅ Bombs at 150 pts (25% chance)
- ✅ Trash can spawning (random X in left 25%, Y=40%)
- ✅ Bomb auto-distance (↑↓ disabled for bombs)
- ✅ Explosion mechanics (-2 lives)

**Visual Feedback:**
- ✅ Swish animation (dead center)
- ✅ Clank animation (rim in)
- ✅ Rim out animation
- ✅ Airball detection
- ✅ Defender block flash
- ✅ Streak counter (3+ in a row)
- ✅ Shot feedback messages

**UX:**
- ✅ Splash screen (5 seconds)
- ✅ HUD (score, lives, best score)
- ✅ Aim indicator
- ✅ Distance bar (when unlocked)
- ✅ Warning at 48 pts (defender incoming)
- ✅ Warning at 98 pts (depth control)
- ✅ Bomb tutorial (first bomb auto-pauses)
- ✅ Game over screen with milestone badges
- ✅ Session stats tracking

**Milestones:**
- ✅ 🥉 50 pts - Defender Beat
- ✅ 🥈 100 pts - 3D Master
- ✅ 🥅 150 pts - Bomb Squad
- ✅ 🔥 200 pts - On Fire
- ✅ 👑 300 pts - Champion
- ✅ 👑 500 pts - Legendary

**Technical:**
- ✅ High score persistence (~/.shotclock/scores.json)
- ✅ File locking (fcntl)
- ✅ Terminal size check (40×15 minimum)
- ✅ SIGWINCH handling (resize detection)
- ✅ Color support with fallback
- ✅ Emoji with ASCII fallback
- ✅ No external dependencies (stdlib only)

**Integration:**
- ✅ State file system (session_<PID>.json)
- ✅ Hook installer script
- ✅ tmux integration support
- ✅ Non-blocking hooks with failure handling
- ✅ 5-second delay before pane opens
- ✅ Stale session cleanup (>1 hour)

**Testing:**
- ✅ Automated test suite
- ✅ Trajectory physics tests
- ✅ Collision detection tests
- ✅ Scoring system tests
- ✅ Progression threshold tests

**Documentation:**
- ✅ README.md
- ✅ QUICKSTART.md
- ✅ intent.md (design doc)
- ✅ In-line code comments

### 📋 Known Limitations

- Hook integration is conceptual (event names not verified with real Claude Code)
- No actual Claude Code status polling yet (hooks write files but game doesn't read them)
- Terminal must support Unicode for best experience
- Physics simplified (direct trajectory, not true angle-based)
- No sound effects yet
- No pause menu
- Bombs always spawn in same Y position

### 🔜 Next Release (v0.2)

**Features:**
- [ ] Claude Code status integration (read state file, show "Claude thinking" banner)
- [ ] Pause menu (P key)
- [ ] Help overlay (? key)
- [ ] Session stats screen
- [ ] Sound effects (terminal beep)
- [ ] Improved physics (proper angle-based trajectory)
- [ ] Better bomb variety (different Y positions)

**Polish:**
- [ ] Smoother animations
- [ ] Better visual feedback
- [ ] Color themes
- [ ] Stats persistence across sessions

### 🎯 Future (v1.0)

- [ ] Port to Go/Rust (single binary)
- [ ] Team leaderboard
- [ ] Daily challenges
- [ ] Shot Clock mode (60-second rounds)
- [ ] Agent-length mode
- [ ] Replay system
- [ ] Config file support
- [ ] Multiple difficulty levels

---

## Testing Notes

All automated tests passing as of 2026-10-21:
```
✅ Trajectory physics
✅ Collision detection
✅ Scoring system
✅ Progression thresholds
```

Manual testing completed for:
- Splash screen flow
- Basic shooting mechanics
- Lives/game over
- Score persistence
- Terminal resize handling
