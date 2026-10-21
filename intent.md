# **intent.md — Terminal Hoops for Claude Code**

> Working title: **Shot Clock** (alternates: *Swish*, *Buzzer Beater*, *While You Wait*, *Brick*). No strong preference yet.

## **1\. Why this exists**

When Claude Code is thinking or running a long task, the developer just watches a spinner. That's dead time. The goal is a tiny arcade game, like Chrome's offline dinosaur, that:

* shows up when the agent starts working,  
* can be played in short bursts (10 seconds to 5 minutes),  
* keeps a persistent high score so there's a reason to come back,  
* **never gets in the way** of the agent's work. The agent finishing, or asking for permission, always wins.

**One-line pitch:** an arcade basketball shootout in your terminal that plays while Claude works.

---

## **2\. Core loop**

1. The hoop slides left and right across the top of the screen.  
2. The player stands at the bottom, aims with the arrow keys, and shoots with Space.  
3. The ball flies in an arc. Every basket is **2 points**.  
4. The game gets harder at fixed score thresholds (see §5).  
5. **5 misses \= game over.** The score at that moment is the final score. The player has to restart to play again.  
6. When Claude finishes, the game pauses and says "Claude's done". The player can go back to Claude, and the run is saved so it resumes on the next prompt.

       ┌─────────────────────────────────────────┐  
        │  SCORE 042   MISSES ● ● ○ ○ ○  BEST 188  │  
        │                                          │  
        │                 ═╦═  ←→                  │   hoop moves  
        │                  ╚╝                      │  
        │                                          │  
        │                  o  ·                    │   ball in flight  
        │              ·                           │  
        │           ·      ▓▓  ←→ defender         │  
        │        /                                 │  
        │      🏀  aim: 52°   distance: ▮▮▮▮▮▯▯     │  
        │  ⏳ Claude is thinking… (00:42)          │  
        └─────────────────────────────────────────┘

---

## **3\. Controls**

| Key | Action |
| ----- | ----- |
| ← / → | Aim left or right (shot direction). Angle range: 30° to 80°. |
| ↑ / ↓ | Aim farther or shorter (shot distance). **Unlocks at 100 pts**, when the hoop starts moving forward and backward. Before that, distance is automatic. 10 discrete distance steps. |
| Space | Shoot |
| p / q / r / ? | Pause / quit back to Claude / restart / help |

**Terminal constraint:** terminals send key *presses* (with OS key-repeat), not key *releases*. So there's no "hold to charge, release to shoot". Aim is set by tapping arrows, then Space fires. This fits the scheme above.

**One shot at a time:** While a ball is in flight, arrow keys adjust the *next* shot's aim (shown in HUD), but Space does nothing until the current ball lands or goes off-screen.

**Bomb controls:** When holding a bomb (150+ pts), ↑/↓ are disabled. Distance is automatic to match the trash can line. Only ←/→ aim matters.

---

## **4\. Scoring**

* **Every basket: 2 points.** Flat scoring, no multipliers, so the thresholds in §5 are easy to read (25 baskets \= defender, etc.).  
* **Bomb into the trash can (150+): \+2 points.**  
* **Bomb explodes outside the trash can: −2 lives** (2 of the 5 misses). Score never goes down, so thresholds can't be lost once reached.  
* **Miss:** counts toward the 5-miss limit. A shot blocked by the defender counts as a miss.  
* **Game over** at 5 misses. Final score \= current score. Compared against the saved best score.

*Parked ideas (not in v1):* buzzer-beater bonus, power-ups.

**Visual feedback for shot quality:**
* **Swish (dead center):** Hoop animates `║` → `╠╣` quick squeeze, "SWISH!" text
* **Rim in (off-center but scores):** Hoop shakes `═╦═` → `≈╤≈` → `═╦═`, "CLANK!"
* **Rim out (miss):** Same shake, ball bounces off at angle, "OFF THE RIM"
* **Airball (miss by >3 chars):** No animation, ball just falls, "AIRBALL"
* **Defender block:** Defender flashes `▓▓` → `▒▒` → `▓▓`, "BLOCKED!" in red

**Streak counter:** Displayed during play (e.g. "🔥 3 in a row"). Resets on any miss.

---

## **5\. Difficulty progression**

| Score | What happens |
| ----- | ----- |
| **0** | Hoop moves left ↔ right at a steady speed. Distance is automatic; only ←/→ aim matters. |
| **50** (25 baskets) | **Defender appears.** He moves left ↔ right between the player and the hoop. If the ball's path lines up with him as it passes, the shot is **blocked** (counts as a miss). |
| **75** (38 baskets) | **Hoop moves faster** left ↔ right. |
| **100** (50 baskets) | **Hoop moves forward and backward** too (closer / farther). ↑/↓ distance control unlocks; the player sets distance as well as direction. |
| **125, 150, 175…** | Every 25 pts, the hoop and defender get a little faster. |
| **150** (75 baskets) | **Bombs.** At random, the player gets a bomb instead of a basketball, and a **trash can** spawns. The bomb must go in the trash can, not the hoop (see below). |

### **Bombs (150+)**

* After 150, each new ball has a **25% chance** (1 in 4) to be a **bomb** (`💣`, ASCII fallback `(*)`). The HUD makes it obvious: "BOMB\! → trash can".
* When a bomb is in hand, a **trash can** (`[▄▄]`) spawns at a **random X position in the left 25% of screen width**, at **Y = 40% from bottom** (between player at 0% and defender at 60%). Each bomb gets a new random trash can position.
* The trash can is **static** once spawned (doesn't move).
* **Bomb distance is automatic** (always correct to hit the trash can line). Player only controls ←/→ aim. ↑/↓ keys are disabled when holding a bomb.
* **The trash can's line is the fuse.** The bomb explodes the moment it crosses the trash can's horizontal line, unless it hits the can.
  * **Hits the trash can** → no explosion, **\+2 points**, the trash can disappears, play continues.
  * **Crosses the trash can line anywhere else** → explodes. **The player loses 2 of their 5 lives** (counts as 2 misses), plus an explosion animation. No points are taken away.
* Because the bomb always explodes at the trash can line, it never reaches the defender or the hoop. Shooting at the hoop is always a guaranteed explosion.

  hoop line       ═╦═  ←→          (farthest)
   defender line          ▓▓ ←→
   trash can line  \[▄▄\] ─────────── 💥 if the bomb crosses here outside the can
   player          💣               (bottom)

* Shooting the bomb at the hoop is never the right move. That's the trick: the player has to notice the swap and switch targets.

### **Defender behaviour**

* Moves steadily left ↔ right on his own line (Y = 60% from bottom), between the shooter and the hoop. A predictable pattern the player learns to time.
* **Hitbox:** Defender is 2 chars wide (`▓▓`). Block occurs when `defender_x - 1 <= ball_x <= defender_x + 2` as the ball crosses the defender's Y line.
* **A block counts as a miss** (toward the 5).
* His speed only increases in the post-100 steps.
* **No height clearance:** All shots exist on the same 2D plane. There's no way to shoot "over" the defender.

---

## **6\. Game modes**

**Default (decided): Endless.** Play until 5 misses, then restart. Best score is saved.

* When Claude stops, the run **pauses** (not ends). The player goes back to Claude, and the same run resumes the next time the agent starts working.
* A run can stretch across many prompts, so a high score can be built up over a whole coding session.
* **After game over during a long Claude task:** Auto-restart after 3 seconds with "Starting new run... (press R to restart now, Q to quit)". Multiple runs per prompt are allowed.
* **Session stats:** Track "baskets this session" separately from all-time high score for motivation even after beating your best.
* **Milestones:** Achievements at 50, 100, 150, 200, 300, 500 pts with emoji badges (🥉🥈🥅🔥👑) shown on game-over screen.

Later modes (not in MVP):

* **Shot Clock:** 60-second rounds, as many points as possible.  
* **Agent-length run:** the round lasts exactly as long as Claude is thinking.  
* **Daily challenge:** fixed seed per day so everyone gets the same hoop pattern.

---

## **7\. Integration with Claude Code (the hard part)**

### **The problem**

Claude Code's UI owns the terminal while it runs. A hook script can't draw a game in that same window or read its keystrokes. The game needs **its own surface**.

### **Options**

| Approach | How | Pros | Cons |
| ----- | ----- | ----- | ----- |
| **tmux split pane** *(decided)* | A hook runs `tmux split-window` and launches the game in a small pane next to or below Claude, **only after Claude has been busy for N seconds**. | Seamless. Claude stays visible. Quick tasks don't pop a pane. | Needs tmux. |
| New terminal window/tab | A hook opens a new window (e.g. `osascript` on macOS, `wt` on Windows, or `kitty @`/`wezterm cli`). | No tmux needed. | Platform-specific. Steals focus. |
| Manual command | The user runs `shotclock` in another pane. The game watches a status file to know when Claude is busy. | Simplest. No hooks needed. | Not automatic. |
| Status line widget | Show "🏀 best: 188" or a "Claude done\!" banner in Claude Code's status line. | Zero friction. | Display only. Good as a companion. |

### **Hook wiring (concept; confirm event names in the current Claude Code hooks docs)**

**State file:** `~/.shotclock/session_<CLAUDE_PID>.json` where `CLAUDE_PID` is Claude Code's process ID (passed via hook env var).

* **When the user submits a prompt** → write `{status: "busy", timestamp: <unix_time>}` to the session file. After **5 seconds** (configurable), if status is still `busy`, launch tmux pane with `shotclock play $CLAUDE_PID`.
* **When Claude needs permission or input** (notification event) → write `{status: "needs_input"}`. The game **pauses immediately** and flashes "⚠️ Claude needs you". Never let a game hide a permission prompt.
* **When Claude stops** → write `{status: "idle"}`. The game **pauses the run** and shows "✅ Claude's done. Press q to go back (your run is saved)". On the next prompt, the run resumes.
* **On session end** → delete the session file, close the pane, save the score to `~/.shotclock/scores.json`.

**File locking:** The game uses `fcntl.flock` (Python) or `syscall.Flock` (Go) when reading/writing session files to prevent race conditions. If locked for >5 seconds, game shows "Waiting for Claude..." and retries.

**Stale session cleanup:** On game launch, if the session file is >1 hour old, assume it's stale and start a fresh run.

The game polls the state file every 100ms, so hooks stay dumb and fast.

### **Etiquette rules**

* Never auto-focus the game pane. The user chooses to tab over.
* Never block or slow down a hook. Hooks just write a file and exit.
* Easy off switch: `SHOTCLOCK=off` or a single settings flag.
* The pane opens only after Claude has been busy for 5 seconds (configurable).

### **Hook failure handling**

```bash
# install-hooks adds this safety check to each hook:
if ! command -v tmux &> /dev/null; then
  echo "⚠️  Shot Clock: tmux not found. Game disabled." >&2
  exit 0
fi

if ! tmux split-window -h "shotclock play $CLAUDE_PID" 2>/dev/null; then
  echo "⚠️  Shot Clock: couldn't open pane. Continuing without game." >&2
  exit 0
fi
```

Hooks always exit 0 (non-blocking). User sees a one-line warning in their terminal; Claude Code continues normally.

---

## **8\. Persistence and social**

* High score and stats in `~/.shotclock/scores.json` (best score, total baskets, "minutes played while waiting on Claude").  
* Paused run state saved alongside, so it survives between prompts.  
* Fun stat at game over: "You made 31 baskets while Claude wrote 1,204 lines."  
* Later: optional team leaderboard and a shareable result string, e.g. `🏀 Shot Clock — 112 pts — reached the moving hoop`

---

## **9\. Look and feel**

* Pure ASCII/Unicode so it works over SSH. Emoji optional with a fallback.
* **Minimum terminal size: 40 cols × 15 rows.** On launch, check with `tput cols` and `tput lines`. If too small, show "Terminal too small for Shot Clock. Need 40×15, have {actual}. Resize or press q." Game waits for resize (via `SIGWINCH`) or quit. No auto-scaling.
* The forward/backward hoop (100+) needs a depth cue: the hoop drawn bigger when close and smaller when far, or a distance number next to it.
* Color with a no-color fallback (`NO_COLOR`).
* **30 fps target.** Simple parabola physics:
  ```
  vx = distance * cos(angle) / flight_time
  vy_initial = distance * sin(angle) / flight_time + 0.5 * gravity * flight_time
  Each frame: x += vx; y += vy; vy += gravity
  gravity = -2.0 (tunable)
  Base flight_time = 1.2 seconds (36 frames at 30fps)
  ```
* Juice: rim "clank" shake, net swish animation, defender "BLOCKED\!" flash.

---

## **10\. Tech stack**

**Decided: prototype in Python** (`curses` or `blessed`), then port to Go or Rust for a single binary, plus a `shotclock install-hooks` command that writes the hook config for you.

---

## **11\. MVP scope (v0.1)**

* \[ \] Python prototype: `shotclock` command, endless mode
* \[ \] Controls: ←/→ direction (30°-80°), ↑/↓ distance (10 steps, unlocks at 100), Space shoot. One shot at a time. Arrow keys adjust next shot while ball in flight.
* \[ \] Ball physics: 1.2s flight time, parabola with tunable gravity (-2.0), lead moving targets
* \[ \] 2 pts per basket; 5 misses \= game over; auto-restart after 3s
* \[ \] Shot feedback: swish/clank/rim-out/airball animations, streak counter
* \[ \] Progression: moving hoop → defender at 50 (with 2-char hitbox) → faster hoop at 75 → forward/back hoop \+ ↑/↓ at 100 → small speed-up every 25 after
* \[ \] Defender moves steadily left↔right on Y=60% line, blocks when aligned with ball; block \= miss
* \[ \] Bombs at 150: 25% chance per ball, trash can spawns random X in left 25% at Y=40%, static, auto-distance, explodes at can line; \+2 in can, −2 lives outside
* \[ \] First-time splash + warnings before defender (48 pts), 3D (98 pts), first bomb (auto-pause with instructions)
* \[ \] Local high score + session stats + milestone badges (🥉🥈🥅🔥👑)
* \[ \] Watches session file `~/.shotclock/session_<PID>.json` with file locking; shows "Claude thinking / Claude done" banner
* \[ \] Pauses on "Claude needs you" and "Claude done"; saves and resumes the run across prompts
* \[ \] `install-hooks` \+ tmux auto-pane after 5s busy (configurable), with failure handling (tmux check, non-blocking hooks)
* \[ \] Terminal size check (40×15 minimum), `SIGWINCH` handling, stale session cleanup (>1hr)

**v0.2:** sound/juice, stats screen **v0.3:** parked scoring ideas (swish, streaks), share string **v1.0:** Go/Rust port, team leaderboard, themes

---

## **12\. Decisions log**

| \# | Decision | Choice |
| ----- | ----- | ----- |
| D1 | Default mode | Endless; **5 misses \= game over**; score at that point is final; player restarts |
| D2 | Claude finishes mid-run | Pause; player goes back to Claude; run is saved and resumes on the next prompt |
| D3 | Launch | Auto tmux pane, only after Claude has been busy for N seconds |
| D4 | Stack | Python prototype first, port to Go/Rust later |
| D5 | Scoring | Flat 2 pts per basket |
| D6 | Progression | 50 defender · 75 faster hoop · 100 hoop moves forward/back |
| D7 | Controls | ←/→ direction, Space shoot; ↑/↓ distance unlocks at 100 (auto-distance before) |
| D8 | Blocks | A defender block counts as a miss |
| D9 | After 100 | Hoop and defender speed up a little every 25 pts |
| D10 | Defender movement | Steady, predictable left↔right |
| D11 | Bombs (150+) | Random bomb instead of a ball; trash can spawns on the left, in front of the defender and hoop; bomb explodes when it crosses the trash can's line unless it hits the can |
| D12 | Bomb outcomes | In the trash can: \+2 pts. Explodes outside: −2 lives (no point loss) |

## **13\. Open questions**

### **Resolved:**
1. ~~N seconds before the pane opens~~ → **5 seconds (configurable)**
2. ~~Pane after Claude finishes~~ → **Stays open paused; shows "Claude's done" message**
3. ~~Can the player keep shooting while Claude is idle?~~ → **Yes, but the run is paused. On next prompt, run resumes.**
4. ~~Bomb frequency~~ → **25% chance (1 in 4 balls)**
5. ~~Trash can placement~~ → **Random X in left 25% of screen, Y=40%, static**
6. ~~Bomb distance control~~ → **Automatic; only ←/→ aim matters**
7. ~~Shot timing~~ → **1.2s flight, player must lead moving targets**
8. ~~Defender collision~~ → **2-char hitbox, no height clearance**
9. ~~Multi-session persistence~~ → **Session file per PID with file locking**

### **Still open:**
1. **Name:** Shot Clock vs. Swish vs. something else? *No preference given yet.*
2. **Speed cap:** Is there a speed cap after 100, or does it keep getting faster until it's impossible?
3. **Life recovery:** With only 5 lives and bombs costing 2, should there be a way to earn a life back (e.g. every 10 baskets)?
4. **Hook events:** Which hook events exactly? Verify against the current Claude Code hooks docs before building.

---

## **14\. Design gap fixes (added 2026-10-21)**

This section documents specifications added to resolve implementation gaps identified during design review.

### **Ball physics & timing**
- **Flight duration:** 1.2 seconds (36 frames at 30 fps)
- **Leading targets:** Player must predict where the hoop will be when the ball arrives
- **Trajectory formula:**
  ```
  vx = distance * cos(angle) / flight_time
  vy_initial = distance * sin(angle) / flight_time + 0.5 * gravity * flight_time
  Each frame: x += vx; y += vy; vy += gravity
  gravity = -2.0 (tunable constant)
  ```
- **Angle range:** 30° (shallow arc) to 80° (high arc)
- **Distance control:** Auto before 100 pts; 10 discrete steps after 100 pts

### **Input handling**
- **One shot at a time:** Space does nothing while a ball is in flight
- **Aim adjustment during flight:** Arrow keys adjust the *next* shot's parameters (displayed in HUD)
- **Bomb controls:** ↑/↓ disabled when holding a bomb; distance is automatic

### **Collision & placement**
- **Defender hitbox:** 2 chars wide. Block when `defender_x - 1 <= ball_x <= defender_x + 2` at Y crossing
- **No height dimension:** All shots on same 2D plane; can't shoot "over" defender
- **Trash can spawn (150+):** Random X in left 25% of screen width, Y = 40% from bottom
- **Trash can per bomb:** New random position for each bomb
- **Trash can movement:** Static once spawned

### **Session management**
- **State file naming:** `~/.shotclock/session_<CLAUDE_PID>.json` (PID from hook env var)
- **File locking:** `fcntl.flock` (Python) or `syscall.Flock` (Go) to prevent race conditions
- **Stale cleanup:** Sessions >1 hour old are discarded on launch
- **Cleanup on exit:** Session file deleted, scores saved to `~/.shotclock/scores.json`

### **Failure handling**
- **Tmux check:** Hooks check for tmux before attempting pane creation
- **Non-blocking hooks:** Always exit 0; show one-line warning on stderr if pane fails
- **Terminal size:** Check 40×15 minimum on launch; show error and wait for resize or quit
- **Resize handling:** Listen for `SIGWINCH`; pause if terminal shrinks below minimum

### **UX improvements**
- **First launch:** 5-second splash explaining basic controls and progression
- **Progression warnings:** HUD flashes at 48 pts (defender incoming), 98 pts (depth control incoming)
- **First bomb tutorial:** Auto-pause with overlay explaining bomb mechanics
- **Session stats:** Track baskets-this-session separately from all-time high
- **Milestone badges:** 🥉(50) 🥈(100) 🥅(150) 🔥(200) 👑(300/500)
- **Auto-restart:** After game over during long Claude task, restart after 3s
- **Shot feedback:** Distinct animations for swish/clank/rim-out/airball/block
- **Streak counter:** "🔥 X in a row" displayed during play

