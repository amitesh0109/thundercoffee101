# Shot Clock: progress summary

_Last updated: 2026-10-21_

An arcade basketball game to play while Claude Code works. The design spec is [intent.md](intent.md).

## Where things stand

There are two versions of the game in this repo:

| Folder | What it is | Status |
|---|---|---|
| [shotclock/](shotclock/) | Standalone Python/curses game. Run `python3 shotclock/shotclock.py` | Playable |
| [shotclock-plugin/](shotclock-plugin/) | Claude Code plugin: the same game in a pane inside Claude Code | Written, type-checked, tested headless; **not yet tried in a live session** |

### Done today

**Python game ([shotclock/shotclock.py](shotclock/shotclock.py))**
- Analysed the original prototype. Shots could only go right, wide misses were free, bombs exploded on frame 1, and the first bomb froze the game. All fixed.
- Rewrote the drawing: court frame, hoop with backboard, rim and net, stick-figure player, defender, top status bar, bottom control bar, and boxed splash, pause and game-over screens. It redraws without flicker and re-lays out on resize.
- New aiming: ←/→ picks where the ball lands. The arc lands exactly there, so you just lead the moving hoop.
- Trajectory preview is a solid Braille-dot curve, with a `×` landing marker.
- Runs at 60 fps; the ball leaves a short trail.
- Arcade effects: "Heating up" at a 3-basket streak and "On fire" at 5 (flaming ball), a crowd that cheers, groans and does the wave, confetti on swishes, rim sparks, "+2" pop-ups, and screen shake on bomb explosions.
- Ball is now the 🏀 emoji (💣 for bombs).
- P pauses; best score saves at game over; longest streak shows on the game-over screen.

**Claude Code plugin ([shotclock-plugin/](shotclock-plugin/))**
- [hooks/register.tsx](shotclock-plugin/hooks/register.tsx) follows what Claude is doing:
  - `turn.start`: marks Claude busy, then opens the pane after 5 s if Claude is still working.
  - `turn.complete`: marks Claude idle, and the game pauses with "Claude's done".
  - `classic.Notification`: marks "needs you", and the game pauses so it never hides a permission prompt.
  - `tool.call`: switches back to busy once the tool runs.
  - `/shotclock` command opens the pane by hand.
  - Best score is kept across sessions in `$.store`.
  - `SHOTCLOCK=off` turns off auto-open.
- [hooks/game.tsx](shotclock-plugin/hooks/game.tsx) is the game, ported to TypeScript as a `Client` module: its own frame timer, keyboard input, and the same visuals as the Python version. Click the court to play; Esc returns to the prompt.
- Type-checks clean with TypeScript 5.6.
- A headless Node run confirmed it draws rows of exactly the pane's width, aimed shots swish, it pauses and resumes with Claude, and game over posts the score back to the hooks module.
- The live copy that Claude Code loads is in `~/.claude/dev-mods/21a361e7-35e8-402a-a721-50088f0ba9fb/shotclock/`. This repo folder is a snapshot of it.

## Open problems and unknowns

- **Untested inside Claude Code.** The plugin hasn't been loaded in a live session yet. The engine's own validation may still flag something.
- **Old CLI.** The `claude` CLI on this machine is 2.0.0 (`/opt/homebrew/bin/claude` and `/usr/local/bin/claude`). Function-hook plugins need a newer build: this session's engine is 2.1.301. Update the CLI before trying the plugin in Terminal.
- **Auto-open needs a wide terminal.** Claude Code only opens a pane unasked at 144+ columns (110+ once you've opened it yourself). Narrower than that, use `/shotclock`.
- **Frame rate unknown.** The pane's timer runs every 33 ms (about 30 fps). It hasn't been measured in a real pane.
- **No VS Code support.** The VS Code extension has no `Client` element, so the game only runs in the terminal and possibly the desktop app. VS Code shows a message instead.
- **Notification heuristic.** Any notification while Claude is busy is treated as "needs you". Check which `notification_type` values actually arrive.

## To do tomorrow

1. **Load the plugin in a real session.** Update the CLI, then run `claude --plugin-dir ~/Documents/thunderCoffee/shotclock-plugin`. Run `claude plugin validate` and `claude --debug` and fix whatever they report.
2. **Check it feels right live:** frame rate, key response, emoji alignment, and pane size docked (fullscreen, 110+ columns) versus inline.
3. **Test the Claude-state flow end to end:** a long prompt opens the pane after 5 s, finishing pauses it, and a permission prompt pauses it and then resumes.
4. **Add a `*.test.ts`** for the plugin and run it with `claude plugin test`.
5. **Pick one source of truth:** develop the plugin from `shotclock-plugin/` with `--plugin-dir`, rather than keeping two copies in sync.
6. **Unfinished game features** (both versions): ↑/↓ distance does nothing yet; the hoop doesn't move forward and back at 100 points; the run isn't saved when the pane closes; no auto-restart after game over.
7. **Python version cleanup:** remove or fix the old tmux installer ([shotclock/install_hooks.py](shotclock/install_hooks.py) writes hooks Claude Code never reads), and make [shotclock/test_game.py](shotclock/test_game.py) test the real game code.
8. **Open design questions** from intent.md §13: final name, a speed cap after 100, and whether lives can be earned back.
