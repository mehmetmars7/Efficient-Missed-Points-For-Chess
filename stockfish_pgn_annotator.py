"""
stockfish_pgn_annotator.py
--------------------------
Annotate PGN files with Stockfish evaluations ([%eval X.XX] after each move).
Output PGNs are compatible with missed_points.py and game_intelligence.py.

Requires:
    pip install chess
    Stockfish binary: https://stockfishchess.org/download/

Usage:
    python stockfish_pgn_annotator.py --input games/ --output annotated/ --stockfish /path/to/stockfish --depth 20
"""

import argparse
import chess
import chess.engine
import chess.pgn
import os
import re
from pathlib import Path


EVAL_TAG_RE = re.compile(r"\[%eval\s+[^\]]+\]\s*")

def analyze_game_with_stockfish(file_path, stockfish_path, depth, output_directory, input_dir_path, opened_output_files):
    with open(file_path) as pgn_file:
        while True:
            game = chess.pgn.read_game(pgn_file)
            if game is None:
                break

            scores = []
            with chess.engine.SimpleEngine.popen_uci(stockfish_path) as engine:
                node = game
                while node.variations:
                    next_node = node.variations[0]
                    board = next_node.board()
                    info = engine.analyse(board, chess.engine.Limit(depth=depth))
                    score = info.get("score", None)
                    if score is not None:
                        cp = score.relative.score(mate_score=10000)
                        evaluation = cp / 100.0
                        if not board.turn:
                            evaluation *= -1
                        scores.append(evaluation)
                    node = next_node

            annotate_game_with_scores(game, scores, file_path, output_directory, input_dir_path, opened_output_files)


def annotate_game_with_scores(game, scores, file_path, output_directory, input_dir_path, opened_output_files):
    node = game
    score_index = 0
    while node.variations:
        next_node = node.variations[0]
        if score_index < len(scores):
            eval_string = f"[%eval {scores[score_index]:.2f}]"
            existing = EVAL_TAG_RE.sub("", next_node.comment).strip() if next_node.comment else ""
            next_node.comment = (eval_string + " " + existing) if existing else eval_string
        node = next_node
        score_index += 1

    relative_path = Path(file_path).relative_to(input_dir_path)
    dest_folder = Path(output_directory) / relative_path.parent
    dest_folder.mkdir(parents=True, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_file_path = dest_folder / f"{base_name}_annotated.pgn"

    # Use 'w' the first time we touch each output file this run to avoid
    # duplicating games on re-runs; use 'a' for subsequent games in the same file.
    mode = 'a' if output_file_path in opened_output_files else 'w'
    opened_output_files.add(output_file_path)
    with open(output_file_path, mode) as annotated_pgn:
        exporter = chess.pgn.FileExporter(annotated_pgn)
        game.accept(exporter)


def main_stockfish(input_dir_path, output_directory, stockfish_path, depth):
    opened_output_files = set()
    for subdir, dirs, files in os.walk(input_dir_path):
        for file in files:
            if file.endswith(".pgn"):
                file_path = os.path.join(subdir, file)
                print(f"Annotating: {file_path}")
                analyze_game_with_stockfish(file_path, stockfish_path, depth, output_directory, input_dir_path, opened_output_files)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Annotate PGN files with Stockfish [%eval] comments."
    )
    parser.add_argument("--input",     required=True, help="Directory containing PGN files to annotate")
    parser.add_argument("--output",    required=True, help="Directory to write annotated PGN files")
    parser.add_argument("--stockfish", required=True, help="Path to the Stockfish binary")
    parser.add_argument("--depth",     type=int, default=20, help="Search depth (default: 20)")
    args = parser.parse_args()
    main_stockfish(args.input, args.output, args.stockfish, args.depth)
