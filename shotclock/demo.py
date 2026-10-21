#!/usr/bin/env python3
"""
Shot Clock - Demo Mode (non-interactive simulation)
Run this to see what the game looks like without needing a full terminal
"""

import time
import random


def clear_screen():
    print("\033[2J\033[H", end="")


def draw_frame(score, lives, streak, hoop_x, defender_x, ball_x, ball_y, player_x, feedback):
    """Draw a single game frame"""
    width = 60
    height = 20

    clear_screen()

    # HUD
    lives_str = "●" * lives + "○" * (5 - lives)
    print(f"  SCORE {score:03d}   LIVES {lives_str}   BEST 188")

    if streak >= 3:
        print(f"  🔥 {streak} in a row")
    else:
        print()

    if feedback:
        print(f"  {feedback:^56}")
    else:
        print()

    print()

    # Game area
    for y in range(height):
        line = [" "] * width

        # Hoop at top (y=3)
        if y == 3:
            if hoop_x - 1 >= 0 and hoop_x + 1 < width:
                line[hoop_x - 1] = "═"
                line[hoop_x] = "╦"
                line[hoop_x + 1] = "═"
        elif y == 4:
            if hoop_x >= 0 and hoop_x + 1 < width:
                line[hoop_x] = "╚"
                line[hoop_x + 1] = "╝"

        # Defender (y=12)
        if score >= 50 and y == 12:
            if defender_x >= 0 and defender_x + 1 < width:
                line[defender_x] = "▓"
                line[defender_x + 1] = "▓"

        # Ball
        if ball_y >= 0 and int(ball_y) == y:
            ball_pos = int(ball_x)
            if 0 <= ball_pos < width:
                line[ball_pos] = "o"

        # Player at bottom (y=17)
        if y == 17:
            if player_x >= 0 and player_x < width:
                line[player_x] = "🏀"

        print("  " + "".join(line))

    print()
    print(f"  aim: 45°   {'[Press Q to quit]':>42}")


def simulate_shot(score, start_x, target_x):
    """Simulate a shot trajectory"""
    frames = 36  # 1.2 seconds at 30fps
    ball_x = start_x
    ball_y = 17

    vx = (target_x - start_x) / 1.2
    vy = (3 - 17) / 1.2 - (0.5 * -2.0 * 1.2)

    for frame in range(frames):
        ball_x += vx * (1/30)
        ball_y += vy * (1/30)
        vy += -2.0 * (1/30)

        if ball_y < 0:
            break

        yield int(ball_x), ball_y


def main():
    print("🏀 SHOT CLOCK - Demo Mode")
    print("\nThis simulates what the game looks like.")
    print("To play for real, run: python3 shotclock.py")
    print("\nStarting demo in 3 seconds...\n")
    time.sleep(3)

    score = 0
    lives = 5
    streak = 0
    hoop_x = 30
    hoop_vx = 1
    defender_x = 25
    defender_vx = 0.8
    player_x = 30

    shots = [
        (True, "✨ SWISH!"),
        (True, "🏀 BASKET!"),
        (False, "OFF THE RIM"),
        (True, "🏀 BASKET!"),
        (True, "✨ SWISH!"),
    ]

    shot_idx = 0

    try:
        while shot_idx < len(shots):
            # Update hoop
            hoop_x += hoop_vx
            if hoop_x <= 5 or hoop_x >= 55:
                hoop_vx *= -1

            # Update defender
            if score >= 50:
                defender_x += defender_vx
                if defender_x <= 5 or defender_x >= 55:
                    defender_vx *= -1

            # Draw idle state
            draw_frame(score, lives, streak, hoop_x, int(defender_x), -1, -1, player_x, "")
            time.sleep(0.5)

            # Shoot!
            target_x = hoop_x + random.randint(-2, 2)
            feedback = ""

            for ball_x, ball_y in simulate_shot(score, player_x, target_x):
                draw_frame(score, lives, streak, hoop_x, int(defender_x), ball_x, ball_y, player_x, "")
                time.sleep(1/30)

            # Score
            made_it, feedback = shots[shot_idx]
            if made_it:
                score += 2
                streak += 1
            else:
                lives -= 1
                streak = 0

            draw_frame(score, lives, streak, hoop_x, int(defender_x), -1, -1, player_x, feedback)
            time.sleep(1.5)

            shot_idx += 1

            if lives == 0:
                break

        # Game over
        clear_screen()
        print("\n" * 5)
        print("  " + "=" * 50)
        print(f"{'GAME OVER':^52}")
        print("  " + "=" * 50)
        print()
        print(f"{'Final Score: ' + str(score):^52}")
        print(f"{'Session Baskets: ' + str(score // 2):^52}")
        print()
        if score >= 50:
            print(f"{'🥉 DEFENDER BEAT':^52}")
        print()
        print(f"{'To play for real:':^52}")
        print(f"{'python3 shotclock.py':^52}")
        print()

    except KeyboardInterrupt:
        print("\n\nDemo interrupted. To play: python3 shotclock.py\n")


if __name__ == "__main__":
    main()
