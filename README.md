# Chess Game Intelligence & Missed Points Calculator

Calculate **Game Intelligence (GI)** and **Missed Points (MP)** from engine-annotated chess PGN files.

## Scripts

### `missed_points.py` — Missed Points
**No external dependencies.** Pure Python stdlib.

Missed Points (MP) is the total expected game-point loss accumulated over all moves. A lower MP means fewer points were left on the board.

```
python missed_points.py game1.pgn game2.pgn ...
python missed_points.py          # processes all *.pgn files in sample_games/
```

### `game_intelligence.py` — Game Intelligence
**No external dependencies.** Pure Python stdlib.

Game Intelligence (GI) measures how well a player converted their position relative to the game result. Normalized to a 0–200 scale (population average ≈ 157.57).

```
python game_intelligence.py game1.pgn game2.pgn ...
python game_intelligence.py          # processes all *.pgn files in sample_games/
```

### `stockfish_pgn_annotator.py` — PGN Annotator
**Requires:** [`python-chess`](https://python-chess.readthedocs.io/) and a [Stockfish binary](https://stockfishchess.org/download/).

```
pip install chess
```

Walks an input directory, annotates every PGN with `[%eval X.XX]` comments using Stockfish, and writes the results to an output directory. The annotated PGNs are directly compatible with `missed_points.py` and `game_intelligence.py`.

```
python stockfish_pgn_annotator.py \
    --input  games/ \
    --output annotated/ \
    --stockfish /path/to/stockfish \
    --depth 20
```

| Argument | Description | Default |
|---|---|---|
| `--input` | Directory containing PGN files | required |
| `--output` | Directory for annotated output PGNs | required |
| `--stockfish` | Path to Stockfish binary | required |
| `--depth` | Search depth | 20 |


---

## Typical workflow

```
# Step 1 — annotate your PGNs with Stockfish
python stockfish_pgn_annotator.py --input games/ --output annotated/ --stockfish ./stockfish --depth 20

# Step 2 — calculate MP and GI from the annotated files
python missed_points.py annotated/my_game_annotated.pgn
python game_intelligence.py annotated/my_game_annotated.pgn
```

---

## WDL model

Both `missed_points.py` and `game_intelligence.py` use a hardcoded WDL model at fixed ply=30, ported directly from [`python-chess`](https://github.com/niklasf/python-chess/blob/master/chess/engine.py) — no `python-chess` install required. The sigmoid formula converts centipawn evaluations to win/draw/loss probabilities:

```
wins = floor(0.5 + 1000 / (1 + exp((a - x) / b)))
```

where `a` and `b` are cubic polynomials in `m = clamp(ply/2 + 1, 8, 120) / 32`  
and `x = clamp(cp × 356 / 100, −4000, 4000)`.

---

## Example output

```
FIDE World Championship Match 2018 - Round 12
Caruana, Fabiano vs Carlsen, Magnus  |  Result: 1/2-1/2
Player                               MP   Elo  Moves
----------------------------------------------------
Caruana, Fabiano (White)         0.8480  2832     31
Carlsen, Magnus (Black)          0.7735  2835     31

FIDE World Championship Match 2021 - Round 6
Carlsen, Magnus vs Nepomniachtchi, Ian  |  Result: 1-0
Player                              GI   Elo  Moves
--------------------------------------------------
Carlsen, Magnus (White)         138.80  2855    136
Nepomniachtchi, Ian (Black)     111.41  2782    135
```

---
## Reference
- Paper: https://doi.org/10.48550/arXiv.2302.13937
- World Championship & super-GM games: https://github.com/drmehmetismail/Performance-Metrics
- Engine vs engine games (CCRL): https://github.com/drmehmetismail/Engine-vs-engine-chess-stats
- Lichess games: https://github.com/drmehmetismail/Chess-Data-Processing

---

## Citation

```bibtex
@misc{seven2025,
      title={Game Intelligence: Theory and Computation}, 
      author={Mehmet Mars Seven},
      year={2025},
      eprint={2302.13937},
      archivePrefix={arXiv},
      primaryClass={econ.TH},
      url={https://arxiv.org/abs/2302.13937}, 
}
```
