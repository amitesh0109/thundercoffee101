#!/usr/bin/env python3
"""
Shot Clock - Terminal basketball game for Claude Code
"""

import curses
import fcntl
import json
import math
import os
import random
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


# Constants
FPS = 60
FRAME_TIME = 1.0 / FPS
ANIM_RATE = 30  # Animation counters below are in 1/30 s steps, whatever the frame rate
FLIGHT_TIME = 1.2  # Seconds from release until the ball drops onto its target line
DISTANCE_STEPS = 10
MIN_WIDTH = 40
MIN_HEIGHT = 15

# Game settings
MAX_LIVES = 5
POINTS_PER_BASKET = 2
DEFENDER_THRESHOLD = 50
SPEED_UP_THRESHOLD = 75
DEPTH_THRESHOLD = 100
BOMB_THRESHOLD = 150
BOMB_CHANCE = 0.25

# Hoop geometry, in columns from the rim's centre
SWISH_HALF = 0.6   # Dead centre
RIM_HALF = 2.0     # Inside the rim: scores
RIM_EDGE = 3.5     # Hits the rim and bounces out; beyond this is an airball

# Streaks
HEATING_UP_STREAK = 3
ON_FIRE_STREAK = 5

# Movement speeds, in columns per second
HOOP_SPEED = 5.0
DEFENDER_SPEED = 4.0

BALL = "🏀"
BOMB = "💣"

MILESTONES = [
    (500, "👑 LEGENDARY"),
    (300, "👑 CHAMPION"),
    (200, "🔥 ON FIRE"),
    (150, "🥅 BOMB SQUAD"),
    (100, "🥈 3D MASTER"),
    (50, "🥉 DEFENDER BEAT"),
]


class GameState(Enum):
    SPLASH = "splash"
    PLAYING = "playing"
    PAUSED = "paused"
    GAME_OVER = "game_over"
    CLAUDE_DONE = "claude_done"


@dataclass
class Ball:
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    g: float = 0.0
    is_bomb: bool = False
    in_flight: bool = False
    live: bool = False     # Can still score or be blocked
    sinking: bool = False  # Dropping through the net after a basket
    trail: deque = field(default_factory=lambda: deque(maxlen=8))


@dataclass
class Hoop:
    x: float = 0.0
    vx: float = HOOP_SPEED


@dataclass
class Defender:
    x: float = 0.0  # Left column of the 2-char body; hitbox is x-1 .. x+2
    vx: float = DEFENDER_SPEED


@dataclass
class TrashCan:
    x: int = 0  # Left column of "[▄▄]"
    active: bool = False


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float      # Seconds left
    text: str
    kind: str        # Attribute name
    gravity: float = 25.0


@dataclass
class GameStats:
    score: int = 0
    lives: int = MAX_LIVES
    misses: int = 0
    streak: int = 0
    session_baskets: int = 0
    best_score: int = 0
    best_streak: int = 0


# Braille dot bits by [sub-row][sub-column]; each character cell holds 2 x 4 dots
BRAILLE_BITS = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))


def braille_cells(points):
    """Plot (x, y) points, in cell units, as braille characters keyed by (row, col)"""
    bits = {}
    for x, y in points:
        sx = math.floor((x + 0.5) * 2)
        sy = math.floor((y + 0.5) * 4)
        cell = (sy // 4, sx // 2)
        bits[cell] = bits.get(cell, 0) | BRAILLE_BITS[sy % 4][sx % 2]
    return {cell: chr(0x2800 + b) for cell, b in bits.items()}


def display_width(text: str) -> int:
    """Terminal columns used by text (emoji take two)"""
    return sum(2 if ord(c) >= 0x1F300 else 1 for c in text)


class ShotClock:
    def __init__(self, stdscr, session_id: Optional[str] = None):
        self.stdscr = stdscr
        self.session_id = session_id or "standalone"
        self.state = GameState.SPLASH
        self.splash_time = 5.0
        self.splash_start = time.time()
        self.pause_reason = ""
        self.tick = 0

        self.stats = GameStats()
        self.ball = Ball()
        self.hoop = Hoop()
        self.defender = Defender()
        self.trash_can = TrashCan()

        self.layout()
        self.hoop.x = self.width / 2
        self.defender.x = self.width / 2 - 1

        # Player aim: horizontal offset (columns) from the player to the target
        self.aim_dx = 0
        self.aim_distance = 5  # 0-9 for 10 steps

        # Animation states
        self.hoop_shake_frames = 0
        self.net_flash_frames = 0
        self.defender_flash_frames = 0
        self.last_feedback = ""
        self.feedback_kind = "good"
        self.feedback_frames = 0
        self.explosion = None  # [x, y, frames_left]
        self.particles = []
        self.popups = []       # Floating text, also Particles
        self.crowd_mood = "idle"
        self.crowd_time = 0.0  # Seconds left in the current mood
        self.crowd_elapsed = 0.0
        self.screen_shake = 0.0
        self.shake_dx = 0
        self.new_best = False

        self.shown_bomb_tutorial = False

        self.load_scores()

        try:
            curses.curs_set(0)
        except curses.error:
            pass
        stdscr.nodelay(True)
        stdscr.keypad(True)
        self.init_colors()
        self.load_next_ball()

    # ------------------------------------------------------------------ setup

    def init_colors(self):
        """Build the attribute palette, falling back to plain styles"""
        names = ["frame", "label", "value", "title", "rim", "net", "board", "ball",
                 "bomb", "player", "defender", "trash", "preview", "good", "bad",
                 "warn", "dim", "panel", "trail"]
        self.attr = {name: curses.A_NORMAL for name in names}
        self.attr.update(value=curses.A_BOLD, title=curses.A_REVERSE | curses.A_BOLD,
                         dim=curses.A_DIM, frame=curses.A_DIM, label=curses.A_DIM,
                         trail=curses.A_DIM, good=curses.A_BOLD, bad=curses.A_BOLD,
                         warn=curses.A_BOLD, ball=curses.A_BOLD, bomb=curses.A_BOLD)

        if os.environ.get("NO_COLOR") or not curses.has_colors():
            return

        curses.start_color()
        try:
            curses.use_default_colors()
            bg = -1
        except curses.error:
            bg = curses.COLOR_BLACK

        rich = curses.COLORS >= 256
        orange = 208 if rich else curses.COLOR_YELLOW
        grey = 244 if rich else curses.COLOR_WHITE
        court = 67 if rich else curses.COLOR_BLUE

        palette = [
            ("frame", court, curses.A_NORMAL),
            ("label", grey, curses.A_NORMAL),
            ("title", orange, curses.A_REVERSE | curses.A_BOLD),
            ("rim", orange, curses.A_BOLD),
            ("net", curses.COLOR_WHITE, curses.A_NORMAL),
            ("board", grey, curses.A_NORMAL),
            ("ball", orange, curses.A_BOLD),
            ("bomb", curses.COLOR_RED, curses.A_BOLD),
            ("player", curses.COLOR_WHITE, curses.A_BOLD),
            ("defender", curses.COLOR_RED, curses.A_BOLD),
            ("trash", curses.COLOR_YELLOW, curses.A_BOLD),
            ("preview", curses.COLOR_CYAN, curses.A_BOLD),
            ("trail", orange, curses.A_DIM),
            ("good", curses.COLOR_GREEN, curses.A_BOLD),
            ("bad", curses.COLOR_RED, curses.A_BOLD),
            ("warn", curses.COLOR_YELLOW, curses.A_BOLD),
            ("dim", grey, curses.A_NORMAL),
            ("panel", orange, curses.A_NORMAL),
        ]
        for pair_id, (name, fg, extra) in enumerate(palette, start=1):
            curses.init_pair(pair_id, fg, bg)
            self.attr[name] = curses.color_pair(pair_id) | extra

    def layout(self):
        """Recompute positions from the current terminal size"""
        self.height, self.width = self.stdscr.getmaxyx()
        h, w = self.height, self.width

        # Row 0 is the HUD, row 1 and h-2 are the court frame, row h-1 is the control bar
        self.top = 2
        self.floor = h - 3
        self.left = 1
        self.right = w - 2

        self.player_x = w // 2
        self.release_y = self.floor - 2
        self.arc_height = max(2, round((self.floor - self.top) * 0.12))
        self.rim_y = self.top + self.arc_height + 1
        span = self.release_y - self.rim_y
        self.defender_y = self.rim_y + max(3, round(span * 0.45))
        self.trash_y = self.rim_y + max(4, round(span * 0.75))

        lo, hi = self.hoop_bounds()
        self.hoop.x = min(max(self.hoop.x, lo), hi)
        lo, hi = self.defender_bounds()
        self.defender.x = min(max(self.defender.x, lo), hi)
        lo, hi = self.trash_bounds()
        self.trash_can.x = min(max(self.trash_can.x, lo), hi)

    def hoop_bounds(self):
        return self.left + 5, self.right - 5

    def defender_bounds(self):
        return self.left + 2, self.right - 3

    def trash_bounds(self):
        lo = self.left + 1
        return lo, max(lo, int(self.width * 0.25) - 4)

    def check_terminal_size(self) -> bool:
        """Check if terminal is large enough"""
        return self.width >= MIN_WIDTH and self.height >= MIN_HEIGHT

    # ------------------------------------------------------------ persistence

    def load_scores(self):
        """Load saved high score"""
        score_file = Path.home() / ".shotclock" / "scores.json"
        try:
            with open(score_file, 'r') as f:
                self.stats.best_score = json.load(f).get('best_score', 0)
        except (OSError, ValueError):
            pass

    def save_scores(self):
        """Save high score, keeping any other saved fields"""
        score_dir = Path.home() / ".shotclock"
        try:
            score_dir.mkdir(exist_ok=True)
            with open(score_dir / "scores.json", 'a+') as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                f.seek(0)
                try:
                    data = json.load(f)
                except ValueError:
                    data = {}
                data['best_score'] = max(data.get('best_score', 0),
                                         self.stats.best_score, self.stats.score)
                data['last_session_baskets'] = self.stats.session_baskets
                f.seek(0)
                f.truncate()
                json.dump(data, f)
                fcntl.flock(f, fcntl.LOCK_UN)
        except OSError:
            pass

    # --------------------------------------------------------------- gameplay

    def target_y(self) -> int:
        return self.trash_y if self.ball.is_bomb else self.rim_y

    def aim_target_x(self) -> int:
        return self.player_x + self.aim_dx

    def clamp_aim(self):
        lo = self.left + 1 - self.player_x
        hi = self.right - 1 - self.player_x
        self.aim_dx = min(max(self.aim_dx, lo), hi)

    def launch_velocity(self, target_x, target_y):
        """Velocity that peaks arc_height rows above target_y and drops onto it after FLIGHT_TIME"""
        rise = self.release_y - (target_y - self.arc_height)
        drop = self.arc_height
        g = 2 * (math.sqrt(rise) + math.sqrt(drop)) ** 2 / FLIGHT_TIME ** 2
        vy = -math.sqrt(2 * g * rise)
        vx = (target_x - self.player_x) / FLIGHT_TIME
        return vx, vy, g

    def aim_angle(self) -> int:
        """Launch angle as it looks on screen (rows are about twice as tall as columns)"""
        vx, vy, _ = self.launch_velocity(self.aim_target_x(), self.target_y())
        return round(math.degrees(math.atan2(-vy * 2, vx)))

    def defender_active(self) -> bool:
        return self.stats.score >= DEFENDER_THRESHOLD

    def speed_steps(self) -> int:
        """Number of 25-point speed bumps after 100"""
        return max(0, (self.stats.score - DEPTH_THRESHOLD) // 25)

    def load_next_ball(self):
        """Put a new ball (or bomb) in the player's hands"""
        self.ball.in_flight = False
        self.ball.is_bomb = (self.stats.score >= BOMB_THRESHOLD and
                             random.random() < BOMB_CHANCE)
        self.trash_can.active = self.ball.is_bomb
        if self.ball.is_bomb:
            self.trash_can.x = random.randint(*self.trash_bounds())
            if not self.shown_bomb_tutorial and self.state == GameState.PLAYING:
                self.shown_bomb_tutorial = True
                self.pause_reason = "bomb"
                self.state = GameState.PAUSED

    def shoot(self):
        """Fire a shot"""
        if self.ball.in_flight:
            return
        b = self.ball
        b.vx, b.vy, b.g = self.launch_velocity(self.aim_target_x(), self.target_y())
        b.x = float(self.player_x)
        b.y = float(self.release_y)
        b.in_flight = True
        b.live = True
        b.sinking = False
        b.trail.clear()

    def flash(self, text, kind="good", frames=36):
        self.last_feedback = text
        self.feedback_kind = kind
        self.feedback_frames = frames

    @property
    def on_fire(self) -> bool:
        return self.stats.streak >= ON_FIRE_STREAK

    def score_basket(self, text, x, y):
        self.stats.score += POINTS_PER_BASKET
        self.stats.streak += 1
        self.stats.best_streak = max(self.stats.best_streak, self.stats.streak)
        self.stats.session_baskets += 1
        self.flash(text, "good")
        self.popup(x, y - 1, f"+{POINTS_PER_BASKET}", "good")

        streak = self.stats.streak
        if streak == HEATING_UP_STREAK:
            self.announce("HEATING UP!", "warn")
            self.set_crowd("cheer", 1.5)
        elif streak == ON_FIRE_STREAK:
            self.announce("YOU'RE ON FIRE!", "bad")
            self.set_crowd("wave", 3.0)
        elif streak > ON_FIRE_STREAK and streak % 5 == 0:
            self.announce(f"UNSTOPPABLE  x{streak}", "bad")
            self.set_crowd("wave", 3.0)
        else:
            self.set_crowd("cheer", 1.2)

    # ---------------------------------------------------------------- effects

    def burst(self, x, y, count, chars, kinds, speed=10.0, up=8.0, life=0.9, gravity=25.0):
        for _ in range(count):
            angle = random.uniform(0, math.pi)
            v = random.uniform(0.4, 1.0) * speed
            self.particles.append(Particle(
                x, y, math.cos(angle) * v * 1.6, -math.sin(angle) * v * 0.8 - up * random.random(),
                random.uniform(0.5, 1.0) * life, random.choice(chars), random.choice(kinds), gravity))

    def popup(self, x, y, text, kind, life=0.9):
        self.popups.append(Particle(x, y, 0, -4.0, life, text, kind, 0))

    def announce(self, text, kind):
        y = (self.rim_y + self.defender_y) // 2 + 1
        self.popups.append(Particle(self.width / 2, y, 0, -1.5, 1.8, text, kind, 0))

    def set_crowd(self, mood, seconds):
        if self.crowd_mood == "wave" and self.crowd_time > 0 and mood != "wave":
            return  # Let the wave finish
        self.crowd_mood, self.crowd_time = mood, seconds
        self.crowd_elapsed = 0.0

    def update_effects(self, dt: float):
        for p in self.particles + self.popups:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vy += p.gravity * dt
            p.life -= dt
        self.particles = [p for p in self.particles if p.life > 0 and p.y < self.floor + 1]
        self.popups = [p for p in self.popups if p.life > 0]

        self.crowd_time -= dt
        self.crowd_elapsed += dt
        if self.crowd_time <= 0:
            self.crowd_mood = "idle"

        self.screen_shake = max(0.0, self.screen_shake - dt)
        self.shake_dx = random.choice((-1, 1)) if self.screen_shake > 0 else 0

        # Flames off a ball that's on fire
        b = self.ball
        if self.on_fire and b.in_flight and not b.is_bomb and len(self.particles) < 80:
            for _ in range(2):
                self.particles.append(Particle(
                    b.x + random.uniform(-0.6, 0.6), b.y, random.uniform(-2, 2),
                    random.uniform(-4, -1), random.uniform(0.15, 0.35),
                    random.choice("^*'`"), random.choice(("bad", "warn", "rim")), -4.0))

    def lose_lives(self, count, text):
        self.stats.misses += count
        self.stats.lives = max(0, self.stats.lives - count)
        self.stats.streak = 0
        self.flash(text, "bad")
        if self.stats.lives == 0:
            self.game_over()
        else:
            self.set_crowd("groan", 0.9)

    def game_over(self):
        self.state = GameState.GAME_OVER
        self.new_best = self.stats.score > self.stats.best_score
        self.stats.best_score = max(self.stats.best_score, self.stats.score)
        self.save_scores()

    @staticmethod
    def crossed(prev_y, y, row) -> bool:
        return prev_y > row >= y or prev_y < row <= y

    @staticmethod
    def x_at_row(prev_x, prev_y, x, y, row) -> float:
        """Where the ball was horizontally when it crossed row during this frame"""
        if y == prev_y:
            return x
        return prev_x + (x - prev_x) * (row - prev_y) / (y - prev_y)

    def update_ball(self, dt: float):
        """Update ball physics"""
        b = self.ball
        if not b.in_flight:
            return

        b.trail.append((b.x, b.y))
        prev_x, prev_y = b.x, b.y
        b.x += b.vx * dt
        b.y += b.vy * dt + 0.5 * b.g * dt * dt
        b.vy += b.g * dt

        if b.sinking:
            # Ride down through the net, then disappear
            b.x = self.hoop.x
            if b.y >= self.rim_y + 2.5:
                self.load_next_ball()
            return

        if b.live and b.is_bomb:
            # The trash can's line is the fuse
            if b.vy > 0 and self.crossed(prev_y, b.y, self.trash_y):
                cross_x = self.x_at_row(prev_x, prev_y, b.x, b.y, self.trash_y)
                if abs(cross_x - (self.trash_can.x + 1.5)) <= 2:
                    self.score_basket("IN THE CAN!", self.trash_can.x + 1.5, self.trash_y)
                    self.burst(self.trash_can.x + 1.5, self.trash_y - 1, 8, "·•°", ["trash", "dim"],
                               speed=5, up=4)
                else:
                    self.explosion = [cross_x, self.trash_y, 18]
                    self.screen_shake = 0.45
                    self.burst(cross_x, self.trash_y, 26, "*#%@·", ["bad", "warn", "rim"],
                               speed=18, up=10, life=1.1)
                    self.lose_lives(2, "BOOM! -2 LIVES")
                if self.state != GameState.GAME_OVER:
                    self.load_next_ball()
                else:
                    b.in_flight = False
                return

        elif b.live:
            if self.defender_active() and self.crossed(prev_y, b.y, self.defender_y):
                cross_x = self.x_at_row(prev_x, prev_y, b.x, b.y, self.defender_y)
                if self.defender.x - 1 <= cross_x <= self.defender.x + 2:
                    b.live = False
                    b.vx *= -0.3
                    b.vy = abs(b.vy) * 0.3
                    self.defender_flash_frames = 12
                    self.lose_lives(1, "BLOCKED!")

            if b.live and b.vy > 0 and self.crossed(prev_y, b.y, self.rim_y):
                dx = self.x_at_row(prev_x, prev_y, b.x, b.y, self.rim_y) - self.hoop.x
                if abs(dx) <= SWISH_HALF:
                    b.live, b.sinking = False, True
                    self.net_flash_frames = 12
                    self.score_basket("SWISH!", self.hoop.x, self.rim_y)
                    self.burst(self.hoop.x, self.rim_y - 1, 22, "*+•·✦", ["good", "warn", "rim", "preview"],
                               speed=12, up=8, life=1.2)
                elif abs(dx) <= RIM_HALF:
                    b.live, b.sinking = False, True
                    self.hoop_shake_frames = 8
                    self.score_basket("CLANK! ...IN", self.hoop.x, self.rim_y)
                    self.burst(self.hoop.x + dx, self.rim_y, 6, "'`,", ["warn"], speed=6, up=3, life=0.4)
                elif abs(dx) <= RIM_EDGE:
                    b.live = False
                    b.vx = math.copysign(10, dx)
                    b.vy = -abs(b.vy) * 0.35
                    self.hoop_shake_frames = 8
                    self.burst(self.hoop.x + dx, self.rim_y, 6, "'`,", ["warn"], speed=6, up=3, life=0.4)
                    self.lose_lives(1, "OFF THE RIM")
                else:
                    b.live = False
                    self.lose_lives(1, "AIRBALL")

        if b.y > self.floor or b.x < self.left or b.x > self.right:
            if b.live:
                self.lose_lives(1, "AIRBALL")
            if self.state != GameState.GAME_OVER:
                self.load_next_ball()
            else:
                b.in_flight = False

    def update_hoop(self, dt: float):
        """Update hoop position"""
        speed = HOOP_SPEED
        if self.stats.score >= SPEED_UP_THRESHOLD:
            speed *= 1.5
        speed *= 1 + 0.1 * self.speed_steps()
        self.hoop.vx = math.copysign(speed, self.hoop.vx)

        self.hoop.x += self.hoop.vx * dt
        lo, hi = self.hoop_bounds()
        if self.hoop.x <= lo:
            self.hoop.x, self.hoop.vx = lo, abs(self.hoop.vx)
        elif self.hoop.x >= hi:
            self.hoop.x, self.hoop.vx = hi, -abs(self.hoop.vx)

    def update_defender(self, dt: float):
        """Update defender position"""
        if not self.defender_active():
            return
        speed = DEFENDER_SPEED * (1 + 0.1 * self.speed_steps())
        self.defender.vx = math.copysign(speed, self.defender.vx)

        self.defender.x += self.defender.vx * dt
        lo, hi = self.defender_bounds()
        if self.defender.x <= lo:
            self.defender.x, self.defender.vx = lo, abs(self.defender.vx)
        elif self.defender.x >= hi:
            self.defender.x, self.defender.vx = hi, -abs(self.defender.vx)

    def tick_animations(self, dt: float):
        step = dt * ANIM_RATE
        for name in ("hoop_shake_frames", "net_flash_frames",
                     "defender_flash_frames", "feedback_frames"):
            if getattr(self, name) > 0:
                setattr(self, name, max(0, getattr(self, name) - step))
        if self.explosion:
            self.explosion[2] -= step
            if self.explosion[2] <= 0:
                self.explosion = None

    # ---------------------------------------------------------------- drawing

    def put(self, y, x, text, attr=curses.A_NORMAL):
        """addstr that clips to the screen instead of raising"""
        y, x = int(y), int(x)
        if not 0 <= y < self.height or not text:
            return
        if self.shake_dx and 2 <= y < self.height - 2 and 0 < x and x + len(text) < self.width:
            x = min(max(1, x + self.shake_dx), self.width - 1 - len(text))  # Court contents only
        if x < 0:
            text, x = text[-x:], 0
        text = text[:max(0, self.width - x)]
        if y == self.height - 1:
            text = text[:max(0, self.width - 1 - x)]  # Writing the last cell raises
        if not text:
            return
        try:
            self.stdscr.addstr(y, x, text, attr)
        except curses.error:
            pass

    def draw(self):
        """Draw the game"""
        self.stdscr.erase()

        self.draw_court()
        self.draw_hud()
        self.draw_bar()

        if self.state == GameState.SPLASH:
            self.draw_splash()
        elif self.state == GameState.GAME_OVER:
            self.draw_game_over()
        elif self.state == GameState.PAUSED:
            self.draw_paused()

        self.stdscr.refresh()

    def draw_court(self):
        w, h = self.width, self.height
        frame = self.attr["frame"]
        self.put(1, 0, "╭" + "─" * (w - 2) + "╮", frame)
        for y in range(self.top, h - 2):
            self.put(y, 0, "│", frame)
            self.put(y, w - 1, "│", frame)
        self.put(h - 2, 0, "╰" + "─" * (w - 2) + "╯", frame)

        self.draw_crowd()
        if self.state == GameState.PLAYING and not self.ball.in_flight:
            self.draw_preview()
        if self.trash_can.active:
            self.draw_trash_can()
        if self.defender_active():
            self.draw_defender()
        self.draw_hoop()
        if self.state == GameState.PLAYING and not self.ball.in_flight:
            self.draw_landing_marker()
        self.draw_player()
        if self.ball.in_flight:
            self.draw_ball()
        if self.explosion:
            self.draw_explosion()
        for p in self.particles:
            self.put(round(p.y), round(p.x), p.text, self.attr[p.kind])
        for p in self.popups:
            self.put(round(p.y), round(p.x) - len(p.text) // 2, p.text, self.attr[p.kind])

        # Shot feedback sits in the top edge of the court
        if self.feedback_frames > 0 and self.state != GameState.GAME_OVER:
            label = f" {self.last_feedback} "
            self.put(1, (w - len(label)) // 2, label, self.attr[self.feedback_kind])

    def draw_braille(self, points, attr):
        for (row, col), char in braille_cells(points).items():
            self.put(row, col, char, attr)

    def draw_crowd(self):
        """Fans along the top of the court; they cheer, groan and do the wave"""
        row = self.top
        mood = self.crowd_mood
        wave_at = self.crowd_elapsed * 45 / 4  # Seat index the wave has reached
        for i, x in enumerate(range(self.left + 2, self.right - 3, 4)):
            seed = (i * 7919 + 3) % 17
            if seed % 6 == 0:
                continue  # Empty seat
            if mood == "cheer":
                up = int(self.tick / 3 + seed) % 2 == 0
            elif mood == "wave":
                up = abs(i - wave_at) < 1.5 or abs(i - (wave_at - 12)) < 1.5
            else:
                up = False

            if up:
                fan, attr = "╲o╱", self.attr["warn" if seed % 2 else "rim"]
            elif mood == "groan":
                fan, attr = "╭o╮", self.attr["dim"]
            else:
                fan, attr = " o ", self.attr["dim"]
            self.put(row, x, fan, attr)

    def draw_preview(self):
        """Solid arc showing where the next shot will go"""
        tx, ty = self.aim_target_x(), self.target_y()
        vx, vy, g = self.launch_velocity(tx, ty)
        steps = 400
        points = []
        for i in range(steps + 1):
            t = FLIGHT_TIME * i / steps
            y = self.release_y + vy * t + 0.5 * g * t * t
            if y > self.release_y - 0.5:
                continue  # Keep the start of the arc off the ball in hand
            points.append((self.player_x + vx * t, y))
        self.draw_braille(points, self.attr["preview"])

    def draw_landing_marker(self):
        """Mark where the previewed shot comes down"""
        self.put(self.target_y(), self.aim_target_x(), "×", self.attr["warn"])

    def draw_hoop(self):
        cx = int(round(self.hoop.x))
        r = self.rim_y
        shake = random.choice((-1, 1)) if self.hoop_shake_frames > 0 else 0
        net_attr = self.attr["good"] if self.net_flash_frames > 0 else self.attr["net"]

        self.put(r - 1, cx - 4, "▄▄▄▄▄▄▄▄▄", self.attr["board"])
        self.put(r, cx - 3 + shake, "o━━━━━o", self.attr["rim"])
        self.put(r + 1, cx - 2, "╲│││╱", net_attr)
        self.put(r + 2, cx - 1, "╲│╱", net_attr)

    def draw_defender(self):
        x = int(round(self.defender.x))
        body = "╲░░╱" if self.defender_flash_frames > 0 else "╲██╱"
        self.put(self.defender_y, x - 1, body, self.attr["defender"])

    def draw_trash_can(self):
        attr = self.attr["trash"]
        if not self.ball.in_flight and int(self.tick) % 20 < 10:
            attr |= curses.A_REVERSE
        self.put(self.trash_y, self.trash_can.x, "[▄▄]", attr)

    def ball_cells(self, x, y):
        """Cells covered by the ball emoji, which is two cells wide, centred on x"""
        row, col = round(y), round(x - 0.5)
        return {(row, col), (row, col + 1)}

    def put_ball(self, x, y, is_bomb):
        self.put(round(y), round(x - 0.5), BOMB if is_bomb else BALL)

    def draw_player(self):
        px = self.player_x
        self.put(self.floor - 1, px - 1, "╲O╱", self.attr["player"])
        self.put(self.floor, px - 1, "╱ ╲", self.attr["player"])
        if not self.ball.in_flight and self.state != GameState.GAME_OVER:
            self.put_ball(px, self.release_y, self.ball.is_bomb)

    def draw_ball(self):
        b = self.ball
        # Trail: a fine line through recent positions, stopping short of the ball
        path = list(b.trail)
        points = []
        for (x0, y0), (x1, y1) in zip(path, path[1:] + [(b.x, b.y)]):
            for i in range(8):
                f = i / 8
                points.append((x0 + (x1 - x0) * f, y0 + (y1 - y0) * f))
        covered = self.ball_cells(b.x, b.y)
        trail = {c: ch for c, ch in braille_cells(points).items() if c not in covered}
        for (row, col), char in trail.items():
            self.put(row, col, char, self.attr["rim" if self.on_fire else "trail"])
        self.put_ball(b.x, b.y, b.is_bomb)
        if b.is_bomb:
            spark = "*" if int(self.tick) % 4 < 2 else "'"
            self.put(round(b.y) - 1, round(b.x) + 2, spark, self.attr["warn"])

    def draw_explosion(self):
        x, y, frames = self.explosion
        attr = self.attr["bad"] if int(frames) % 4 < 2 else self.attr["warn"]
        art = [" ╲ │ ╱ ", "── ✷ ──", " ╱ │ ╲ "] if frames > 6 else ["  · ", " ·✷· ", "  · "]
        for i, line in enumerate(art):
            self.put(y - 1 + i, round(x) - len(line) // 2, line, attr)

    def draw_hud(self):
        A = self.attr
        s = self.stats
        segments = []
        if self.width >= 70:
            segments += [(" SHOT CLOCK ", A["title"]), ("  ", 0)]
        else:
            segments += [(" ", 0)]
        segments += [("SCORE ", A["label"]), (f"{s.score:03d}", A["value"]), ("   ", 0),
                     ("LIVES ", A["label"]), ("●" * s.lives, A["bad"]),
                     ("○" * (MAX_LIVES - s.lives), A["dim"])]
        if self.on_fire:
            flicker = A["bad"] if int(self.tick / 4) % 2 else A["warn"]
            segments += [("   ", 0), (f"ON FIRE x{s.streak}", flicker)]
        elif s.streak >= 2:
            segments += [("   ", 0), (f"STREAK x{s.streak}", A["warn"])]

        x = 0
        for text, attr in segments:
            self.put(0, x, text, attr)
            x += len(text)

        best = f"{max(s.best_score, s.score):03d} "
        if x + len(best) + 6 < self.width:
            self.put(0, self.width - len(best) - 5, "BEST ", A["label"])
            self.put(0, self.width - len(best), best, A["value"])

    def draw_bar(self):
        A = self.attr
        y = self.height - 1
        x = 1
        aim = f"AIM {self.aim_angle():>3}°"
        self.put(y, x, aim, A["value"])
        x += len(aim)

        if self.stats.score >= DEPTH_THRESHOLD and not self.ball.is_bomb:
            bars = "▮" * (self.aim_distance + 1) + "▯" * (DISTANCE_STEPS - self.aim_distance - 1)
            dist = f"  DIST {bars}"
            self.put(y, x, dist, A["value"])
            x += len(dist)

        notice, notice_attr = "", 0
        if self.ball.is_bomb and self.state == GameState.PLAYING:
            notice, notice_attr = "BOMB! → TRASH CAN [▄▄]", A["bad"]
        elif 48 <= self.stats.score < DEFENDER_THRESHOLD:
            notice, notice_attr = "Defender incoming at 50!", A["warn"]
        elif 98 <= self.stats.score < DEPTH_THRESHOLD:
            notice, notice_attr = "Depth control at 100: ↑↓", A["warn"]

        hints = ["←→ aim  SPACE shoot  P pause  Q quit",
                 "SPACE shoot  P pause  Q quit",
                 "SPACE shoot  Q quit", ""]
        room = self.width - x - 2 - (len(notice) + 6 if notice else 0)
        hint = next(h for h in hints if len(h) <= room)
        hint_x = self.width - len(hint) - 2
        self.put(y, hint_x, hint, A["label"])

        if notice:
            # Centre the notice in the gap between the aim readout and the hints
            gap_left, gap_right = x + 3, hint_x - 3
            nx = max(gap_left, (gap_left + gap_right - len(notice)) // 2)
            self.put(y, nx, notice, notice_attr)

    def draw_panel(self, lines):
        """Centred box over the court; lines are (text, attr) pairs"""
        inner = max(display_width(text) for text, _ in lines) + 6
        bw = min(inner, self.width - 4)
        bh = len(lines) + 4
        y0 = max(1, (self.height - bh) // 2)
        x0 = (self.width - bw) // 2
        border = self.attr["panel"]

        self.put(y0, x0, "╭" + "─" * (bw - 2) + "╮", border)
        for i in range(1, bh - 1):
            self.put(y0 + i, x0, "│", border)
            self.put(y0 + i, x0 + 1, " " * (bw - 2))
            self.put(y0 + i, x0 + bw - 1, "│", border)
        self.put(y0 + bh - 1, x0, "╰" + "─" * (bw - 2) + "╯", border)

        for i, (text, attr) in enumerate(lines):
            tx = x0 + max(1, (bw - display_width(text)) // 2)
            self.put(y0 + 2 + i, tx, text, attr)

    def draw_splash(self):
        A = self.attr
        self.draw_panel([
            ("S H O T   C L O C K", A["rim"]),
            ("", 0),
            ("Sink baskets while Claude works.", 0),
            ("", 0),
            ("←/→  aim        SPACE  shoot", A["value"]),
            ("P    pause      Q      quit ", A["value"]),
            ("", 0),
            ("Lead the hoop - it keeps moving.", A["label"]),
            ("5 misses and you're out.", A["label"]),
            ("", 0),
            ("press any key", A["warn"]),
        ])

    def draw_paused(self):
        A = self.attr
        if self.pause_reason == "bomb":
            lines = [
                ("BOMB!", A["bad"]),
                ("", 0),
                ("Don't shoot this one at the hoop.", 0),
                ("Drop it in the trash can  [▄▄]", A["trash"]),
                ("", 0),
                ("If it falls past the can's line", A["label"]),
                ("anywhere else, it blows up and", A["label"]),
                ("costs 2 lives.", A["label"]),
                ("", 0),
                ("press any key", A["warn"]),
            ]
        else:
            lines = [("PAUSED", A["value"]), ("", 0), ("P resume   Q quit", A["label"])]
        self.draw_panel(lines)

    def draw_game_over(self):
        A = self.attr
        s = self.stats
        lines = [
            ("GAME OVER", A["bad"]),
            ("", 0),
            (f"Score  {s.score}", A["value"]),
            ("NEW BEST!" if self.new_best else f"Best   {s.best_score}",
             A["good"] if self.new_best else A["label"]),
            (f"Baskets this session  {s.session_baskets}", A["label"]),
            (f"Longest streak  {s.best_streak}", A["label"]),
        ]
        milestone = next((m for pts, m in MILESTONES if s.score >= pts), "")
        if milestone:
            lines += [("", 0), (milestone, A["warn"])]
        lines += [("", 0), ("R restart   Q quit", A["value"])]
        self.draw_panel(lines)

    def draw_too_small(self):
        self.stdscr.erase()
        lines = [f"Shot Clock needs {MIN_WIDTH}×{MIN_HEIGHT}",
                 f"have {self.width}×{self.height}",
                 "resize or press q"]
        for i, line in enumerate(lines):
            self.put(self.height // 2 - 1 + i, (self.width - len(line)) // 2, line)
        self.stdscr.refresh()

    # ------------------------------------------------------------------ input

    def handle_input(self):
        """Handle all pending keys; returns False to quit"""
        while True:
            try:
                key = self.stdscr.getch()
            except curses.error:
                return True
            if key == -1:
                return True
            if not self.handle_key(key):
                return False

    def handle_key(self, key):
        if key == curses.KEY_RESIZE:
            return True
        if key in (ord('q'), ord('Q')):
            return False
        if not self.check_terminal_size():
            return True

        if self.state == GameState.SPLASH:
            self.state = GameState.PLAYING
            return True

        if self.state == GameState.GAME_OVER:
            if key in (ord('r'), ord('R')):
                self.reset_game()
            return True

        if self.state == GameState.PAUSED:
            if self.pause_reason == "bomb" or key in (ord('p'), ord('P')):
                self.state = GameState.PLAYING
            return True

        if key == curses.KEY_LEFT:
            self.aim_dx -= 1
            self.clamp_aim()
        elif key == curses.KEY_RIGHT:
            self.aim_dx += 1
            self.clamp_aim()
        elif key == curses.KEY_UP:
            if self.stats.score >= DEPTH_THRESHOLD and not self.ball.is_bomb:
                self.aim_distance = min(DISTANCE_STEPS - 1, self.aim_distance + 1)
        elif key == curses.KEY_DOWN:
            if self.stats.score >= DEPTH_THRESHOLD and not self.ball.is_bomb:
                self.aim_distance = max(0, self.aim_distance - 1)
        elif key == ord(' '):
            self.shoot()
        elif key in (ord('p'), ord('P')):
            self.pause_reason = "pause"
            self.state = GameState.PAUSED
        elif key in (ord('r'), ord('R')):
            self.reset_game()

        return True

    def reset_game(self):
        """Reset game state"""
        self.stats.score = 0
        self.stats.lives = MAX_LIVES
        self.stats.misses = 0
        self.stats.streak = 0
        self.new_best = False
        self.explosion = None
        self.feedback_frames = 0
        self.particles, self.popups = [], []
        self.screen_shake = 0.0
        self.state = GameState.PLAYING
        self.load_next_ball()

    # ------------------------------------------------------------------- loop

    def run(self):
        """Main game loop"""
        last_time = time.time()

        while True:
            frame_start = time.time()
            dt = min(frame_start - last_time, 0.1)  # No big jumps after a stall
            last_time = frame_start

            if not self.handle_input():
                break

            self.layout()
            self.clamp_aim()
            if not self.check_terminal_size():
                self.draw_too_small()
                time.sleep(0.1)
                continue

            if self.state == GameState.PLAYING:
                self.update_ball(dt)
                self.update_hoop(dt)
                self.update_defender(dt)
                self.tick_animations(dt)
                self.update_effects(dt)
            elif self.state == GameState.GAME_OVER:
                self.tick_animations(dt)
                self.update_effects(dt)
            elif self.state == GameState.SPLASH:
                if frame_start - self.splash_start > self.splash_time:
                    self.state = GameState.PLAYING

            self.tick += dt * ANIM_RATE
            self.draw()

            time.sleep(max(0.0, FRAME_TIME - (time.time() - frame_start)))

        # Save scores on exit
        self.save_scores()


def main(stdscr):
    """Entry point for curses"""
    game = ShotClock(stdscr)
    game.run()


if __name__ == "__main__":
    os.environ.setdefault("ESCDELAY", "25")
    curses.wrapper(main)
