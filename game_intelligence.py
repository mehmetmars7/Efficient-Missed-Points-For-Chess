"""
game_intelligence.py
--------------------
Calculate Game Intelligence (GI) from engine-annotated PGN files.

GI measures how well a player converted their position relative to the game result.
It is normalized to a 0–200 scale (average ~157.57 for a random player).

WDL model: Stockfish 16.1, fixed ply=30 — exact port of python-chess _sf16_1_wins().
Reference: https://github.com/niklasf/python-chess/blob/master/chess/engine.py

Usage:
    python game_intelligence.py game1.pgn game2.pgn ...
    python game_intelligence.py          # runs on all *.pgn files next to the script
"""

import math
import re
import sys
import glob
import os


# ---------------------------------------------------------------------------
# WDL model (ply=30 fixed)
# ---------------------------------------------------------------------------

def _wdl_wins(cp: int, ply: int = 30) -> int:
    """Return wins per 1000 from the side-to-move's perspective."""
    normalize = 356
    m = min(120, max(8, ply / 2 + 1)) / 32
    a = (((-1.06249702 * m + 7.42016937) * m + 0.89425629) * m) + 348.60356174
    b = (((-5.33122190 * m + 39.57831533) * m + -90.84473771) * m) + 123.40620748
    x = min(4000, max(cp * normalize / 100, -4000))
    return int(0.5 + 1000 / (1 + math.exp((a - x) / b)))


def cp_to_wdl(cp: int, ply: int = 30) -> tuple[int, int, int]:
    """Return (wins, draws, losses) per 1000 from the perspective of the side to move."""
    wins = _wdl_wins(cp, ply)
    losses = _wdl_wins(-cp, ply)
    draws = 1000 - wins - losses
    return wins, draws, losses


def calculate_expected_value(
    win_prob: float,
    draw_prob: float,
    loss_prob: float,
    turn: str,
    wdl_values: tuple[float, float, float],
) -> tuple[float, float]:
    """Return (exp_white, exp_black) from WDL probabilities of the side to move."""
    win_val, draw_val, loss_val = wdl_values
    if turn == "White":
        exp_white = win_prob * win_val + draw_prob * draw_val + loss_prob * loss_val
        exp_black = loss_prob * win_val + draw_prob * draw_val + win_prob * loss_val
    else:
        exp_white = loss_prob * win_val + draw_prob * draw_val + win_prob * loss_val
        exp_black = win_prob * win_val + draw_prob * draw_val + loss_prob * loss_val
    return exp_white, exp_black


# ---------------------------------------------------------------------------
# GI calculation
# ---------------------------------------------------------------------------

def calculate_gi(
    evals: list[float],
    result: str,
    wdl_values: tuple[float, float, float] = (1.0, 0.5, 0.0),
    ply: int = 30,
) -> tuple | None:
    """
    Compute Game Intelligence (GI) for both players from a list of pawn evaluations.

    GI = normalize(result - sum_of_point_losses), scaled to a 0–200 range.
    The game result string is required to anchor the GI calculation.

    Args:
        evals:      Ordered list of engine evaluations in pawns (from the PGN).
        result:     Game result string: "1-0", "0-1", or "1/2-1/2".
        wdl_values: (win, draw, loss) point values. Default: (1.0, 0.5, 0.0).
        ply:        Fixed ply passed to the WDL model. Default: 30.

    Returns:
        (white_gi, black_gi, white_moves, black_moves), or None if fewer than 2 evaluations.
    """
    if len(evals) < 2:
        return None

    pawns = [evals[0]] + list(evals)

    white_gpl = 0.0
    black_gpl = 0.0
    white_moves = 0
    black_moves = 0
    win_val = wdl_values[0]

    postmove_exp_white = postmove_exp_black = 0.0

    for i in range(1, len(pawns)):
        turn = "White" if i % 2 == 0 else "Black"
        premove_cp = int(100 * pawns[i - 1])
        postmove_cp = int(100 * pawns[i])

        pre_w, pre_d, pre_l = cp_to_wdl(premove_cp, ply)
        post_w, post_d, post_l = cp_to_wdl(postmove_cp, ply)

        premove_exp_white, premove_exp_black = calculate_expected_value(
            pre_w / 1000, pre_d / 1000, pre_l / 1000, turn, wdl_values
        )
        postmove_exp_white, postmove_exp_black = calculate_expected_value(
            post_w / 1000, post_d / 1000, post_l / 1000, turn, wdl_values
        )

        if turn == "Black":
            white_gpl += postmove_exp_white - premove_exp_white
            white_moves += 1
        else:
            black_gpl += premove_exp_black - postmove_exp_black
            black_moves += 1

    if result == "1/2-1/2":
        white_gi = wdl_values[1] - white_gpl
        black_gi = wdl_values[1] - black_gpl
    elif result == "1-0":
        white_gi = wdl_values[0] - white_gpl
        black_gi = wdl_values[2] - black_gpl
    elif result == "0-1":
        black_gi = wdl_values[0] - black_gpl
        white_gi = wdl_values[2] - white_gpl
    else:
        white_gi = postmove_exp_white - white_gpl
        black_gi = postmove_exp_black - black_gpl

    white_gi /= win_val
    black_gi /= win_val

    def normalize_gi(gi: float) -> float:
        return 157.57 + 18.55 * gi

    return normalize_gi(white_gi), normalize_gi(black_gi), white_moves, black_moves


# ---------------------------------------------------------------------------
# PGN parsing
# ---------------------------------------------------------------------------

def _strip_variations(text: str) -> str:
    """Remove side-variation blocks (parenthesised, possibly nested) from movetext."""
    depth = 0
    out = []
    for ch in text:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif depth == 0:
            out.append(ch)
    return ''.join(out)


def parse_pgn(text: str) -> list[dict]:
    """Parse one or more games from a PGN string. Returns games with [%eval] annotations."""
    games = []
    for segment in re.split(r'(?=\[Event )', text):
        segment = segment.strip()
        if not segment:
            continue
        headers: dict[str, str] = {}
        for m in re.finditer(r'\[(\w+)\s+"([^"]*)"\]', segment):
            headers[m.group(1)] = m.group(2)
        evals: list[float] = []
        for m in re.finditer(r'\[%eval\s+(#?[-+]?\d+\.?\d*)\]', _strip_variations(segment)):
            s = m.group(1)
            evals.append(100.0 if s.startswith('#') and int(s[1:]) > 0 else
                         -100.0 if s.startswith('#') else float(s))
        if evals:
            games.append({"headers": headers, "evals": evals})
    return games


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def process_file(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        text = f.read()

    games = parse_pgn(text)
    if not games:
        print(f"[{path}] No games with [%eval] annotations found.\n")
        return

    for game in games:
        h = game["headers"]
        white     = h.get("White", "White")
        black     = h.get("Black", "Black")
        event     = h.get("Event", "")
        round_    = h.get("Round", "?")
        white_elo = h.get("WhiteElo", "-")
        black_elo = h.get("BlackElo", "-")
        result    = h.get("Result", "*")

        result_ = calculate_gi(game["evals"], result)
        if result_ is None:
            print(f"[{path}] Skipped (fewer than 2 evals).\n")
            continue

        white_gi, black_gi, white_moves, black_moves = result_

        print(f"{event} - Round {round_}")
        print(f"{white} vs {black}  |  Result: {result}")
        print(f"{'Player':<30} {'GI':>7} {'Elo':>5} {'Moves':>6}")
        print("-" * 50)
        print(f"{white + ' (White)':<30} {white_gi:>7.2f} {white_elo:>5} {white_moves:>6}")
        print(f"{black + ' (Black)':<30} {black_gi:>7.2f} {black_elo:>5} {black_moves:>6}")
        print()


def main() -> None:
    paths = sys.argv[1:]
    if not paths:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        paths = sorted(glob.glob(os.path.join(script_dir, "sample_games", "*.pgn")))
    if not paths:
        print("Usage: python game_intelligence.py game1.pgn [game2.pgn ...]")
        print("       (or run with no arguments to process all *.pgn in sample_games/)")
        sys.exit(1)
    for path in paths:
        process_file(path)


if __name__ == "__main__":
    main()
