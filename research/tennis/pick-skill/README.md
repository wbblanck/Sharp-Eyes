# Pick skill (6 Nov 2026)

Does a list wallet's pick beat the price it paid, and the price a follower
could get 30 s later? Report: project files `sharp-traders/tennis/pick-skill/`.

    uv run python research/tennis/pick-skill/picks.py data/history-tennis picks.csv
    uv run python research/tennis/pick-skill/skill.py picks.csv frozen-list-2026-10-29.csv
