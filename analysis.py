"""Answers to the five case questions -- Physa technical case.

Analysis layer: imports the simulation engine and adds aggregation plus
confidence intervals. The engine knows nothing about this module.

Conventions
-----------
- Headline numbers use N_GAMES (10,000), as the assignment asks.
- Every estimate carries a 95% confidence interval. At 10,000 games that is
  about +-1.0 percentage point on a probability near 0.5.
- N_CHECK (100,000) is reported alongside Q1 as a convergence check.
- "Rolls per game" is the total across both players; the per-player split is
  reported as a sensitivity.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from snakes_and_ladders import SEEDS, Board, GameResult, GameRules, ExperimentRunner

N_GAMES = 10_000
N_CHECK = 100_000
Z95 = 1.96


@dataclass(frozen=True)
class Estimate:
    """A number and its 95% confidence interval, so neither travels alone."""

    value: float
    margin: float

    def __str__(self) -> str:
        return f"{self.value:.2f} +- {self.margin:.2f}"

    def as_pct(self) -> str:
        return f"{self.value:.1%} +- {self.margin:.1%} p.p."


def proportion(successes: int, n: int) -> Estimate:
    """95% CI for a proportion. Standard error is sqrt(p(1-p)/n)."""
    p = successes / n
    return Estimate(p, Z95 * math.sqrt(p * (1 - p) / n))


def mean(values: list[float]) -> Estimate:
    """95% CI for a mean. Standard error is stdev/sqrt(n)."""
    n = len(values)
    return Estimate(
        statistics.fmean(values), Z95 * statistics.stdev(values) / math.sqrt(n)
    )


def run(board: Board, rules: GameRules, seed: int, n: int) -> list[GameResult]:
    """Simulates one scenario."""
    return ExperimentRunner(board, rules, seed).run(n)


def win_rate(results: list[GameResult]) -> Estimate:
    """Share of games won by player 1."""
    return proportion(sum(r.winner_index == 0 for r in results), len(results))


def q1(board: Board, n: int = N_GAMES) -> dict:
    """P(player 1 wins) in a fair game.

    Players never interact, so player 1 wins whenever he needs no more turns
    than player 2 -- which gives P(win) = 0.5 + P(tie in turns)/2. The implied
    tie probability is reported as a sanity check.
    """
    results = run(board, GameRules(), SEEDS["q1_baseline"], n)
    p1 = win_rate(results)
    return {"p1": p1, "tie_prob": 2 * (p1.value - 0.5), "results": results}


def q2(board: Board, n: int = N_GAMES) -> dict:
    """Snakes players slide down per game.

    Player 2 meets fewer snakes because the loser's race is truncated: the
    game stops on the winning roll, so he never finishes the board. The solo
    run is the untruncated reference.
    """
    results = run(board, GameRules(), SEEDS["q2_snakes"], n)
    solo = run(
        board,
        GameRules(start_positions=(1,), immunities=(0,)),
        SEEDS["solo_reference"],
        n,
    )
    return {
        "total": mean([r.total_snakes for r in results]),
        "p1": mean([r.snakes_per_player[0] for r in results]),
        "p2": mean([r.snakes_per_player[1] for r in results]),
        "solo": mean([r.total_snakes for r in solo]),
        "results": results,
    }


def q3(board: Board, n: int = N_GAMES) -> dict:
    """Rolls to finish a game when each ladder works only half the time."""
    results = run(board, GameRules(ladder_success_prob=0.5), SEEDS["q3_ladder_50"], n)
    baseline = run(board, GameRules(), SEEDS["q1_baseline"], n)

    total = mean([r.total_rolls for r in results])
    base = mean([r.total_rolls for r in baseline])
    return {
        "total": total,
        "p1": mean([r.rolls_per_player[0] for r in results]),
        "p2": mean([r.rolls_per_player[1] for r in results]),
        "baseline": base,
        "increase_pct": 100 * (total.value / base.value - 1),
        "results": results,
    }


def q4(
    board: Board, n: int = N_GAMES, n_refine: int = N_CHECK, finalists: int = 3
) -> dict:
    """Starting square for player 2 that balances the odds.

    Stage 1 sweeps squares one at a time and stops a few squares after player
    1 falls below 45%. The buffer matters because the curve is not monotonic:
    snake heads (12, 14, 17) are bad starting squares and ladder bases are
    worth more than their number suggests.

    Stage 2 re-runs the closest squares with n_refine games. At 10,000 games
    the CI is wider than the gap between neighbouring squares, so the stage-1
    ranking is partly noise.

    A starting square is not "landed on", so starting on a ladder base does
    not climb it.
    """
    sweep: list[tuple[int, Estimate]] = []
    below = 0

    for square in range(1, board.size):
        rules = GameRules(start_positions=(1, square))
        estimate = win_rate(run(board, rules, SEEDS["q4_start_sweep"] + square, n))
        sweep.append((square, estimate))

        if estimate.value < 0.45:
            below += 1
            if below == 4:
                break

    closest = sorted(sweep, key=lambda pair: abs(pair[1].value - 0.5))[:finalists]
    refined = [
        (
            square,
            win_rate(
                run(
                    board,
                    GameRules(start_positions=(1, square)),
                    SEEDS["q4_refine"] + square,
                    n_refine,
                )
            ),
        )
        for square, _ in closest
    ]
    best_square, best = min(refined, key=lambda pair: abs(pair[1].value - 0.5))
    return {
        "best_square": best_square,
        "best": best,
        "sweep": sweep,
        "refined": refined,
        "n_refine": n_refine,
    }


def q5(board: Board, n: int = N_GAMES) -> dict:
    """P(player 1 wins) when player 2 ignores the first snake he meets."""
    results = run(board, GameRules(immunities=(0, 1)), SEEDS["q5_immunity"], n)
    baseline = run(board, GameRules(), SEEDS["q1_baseline"], n)

    p1, base = win_rate(results), win_rate(baseline)
    return {
        "p1": p1,
        "baseline": base,
        "shift_pp": 100 * (p1.value - base.value),
        "results": results,
    }


def main() -> None:
    board = Board.create_physa_test_board()
    line = "-" * 62

    print(f"\n{line}\nQ1 -- Does the starting player have an edge?\n{line}")
    a1 = q1(board)
    print(f"P(player 1 wins) = {a1['p1'].as_pct()}")
    print(f"  implies P(tie in turns) = {a1['tie_prob']:.1%}")
    print(f"  {N_CHECK:,} games: {q1(board, N_CHECK)['p1'].as_pct()}")

    print(f"\n{line}\nQ2 -- Snakes per game\n{line}")
    a2 = q2(board)
    print(f"Snakes per game (both players) = {a2['total']}")
    print(f"  player 1: {a2['p1']}     player 2: {a2['p2']}")
    print(f"  solo race, no truncation: {a2['solo']}")

    print(f"\n{line}\nQ3 -- Rolls per game with 50% ladders\n{line}")
    a3 = q3(board)
    print(f"Rolls per game (both players) = {a3['total']}")
    print(f"  player 1: {a3['p1']}   player 2: {a3['p2']}")
    print(f"  baseline (ladders always work): {a3['baseline']}")
    print(f"  effect: {a3['increase_pct']:+.1f}% longer")

    print(f"\n{line}\nQ4 -- Balancing starting square for player 2\n{line}")
    a4 = q4(board)
    print(f"Sweep at {N_GAMES:,} games per square:")
    for square, e in a4["sweep"]:
        print(f"  P2 starts on {square:>2}: P(P1 wins) = {e.as_pct()}")
    print(f"\nClosest squares re-run at {a4['n_refine']:,} games:")
    for square, e in a4["refined"]:
        mark = " <-- best" if square == a4["best_square"] else ""
        print(f"  P2 starts on {square:>2}: P(P1 wins) = {e.as_pct()}{mark}")
    print(f"\nAnswer: square {a4['best_square']} ({a4['best'].as_pct()})")

    print(f"\n{line}\nQ5 -- Player 2 immune to the first snake\n{line}")
    a5 = q5(board)
    print(f"P(player 1 wins) = {a5['p1'].as_pct()}")
    print(f"  baseline: {a5['baseline'].as_pct()}")
    print(f"  effect: {a5['shift_pp']:+.1f} percentage points")


if __name__ == "__main__":
    main()
