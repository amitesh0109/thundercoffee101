#!/usr/bin/env bash
# Quick launcher for Shot Clock

cd "$(dirname "$0")"

# Check terminal size
cols=$(tput cols)
rows=$(tput lines)

if [ "$cols" -lt 40 ] || [ "$rows" -lt 15 ]; then
    echo "⚠️  Terminal too small. Need 40×15, have ${cols}×${rows}"
    echo "Please resize your terminal and try again."
    exit 1
fi

# Run the game
python3 shotclock.py
