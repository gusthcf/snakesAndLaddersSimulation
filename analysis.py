"""Answers to the five case questions -- Physa technical case.

Analysis layer. Imports the simulation core and adds aggregation and
confidence intervals. The core knows nothing about this module.

Reporting conventions
---------------------
- Headline numbers use N_GAMES (10,000), as the assignment asks.
- Every estimate carries a 95% confidence interval, since 10,000 games leave
  roughly +-1.0 percentage point of sampling error on a probability near 0.5.
- N_GAMES_CHECK (100,000) is reported alongside as a convergence check.
- "Rolls per game" is the total across both players; the per-player split is
  reported as a sensitivity.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from snakes_and_ladders import (
    SEEDS,
    Board,
    GameResult,
    GameRules,
    ExperimentRunner,
)

N_GAMES = 10_000
N_GAMES_CHECK = 100_000
Z95 = 1.96


# --------------------------------------------------------------------------- #
# Estimates with uncertainty
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Estimate:
    """A point estimate with its 95% confidence interval half-width."""

    value: float
    half_width: float
    n: int

    @property
    def low(self) -> float:
        return self.value - self.half_width

    @property
    def high(self) -> float:
        return self.value + self.half_width

    def as_percent(self) -> str:
        return f"{self.value:.1%} +- {self.half_width:.1%} p.p."

    def as_number(self, digits: int = 2) -> str:
        return f"{self.value:.{digits}f} +- {self.half_width:.{digits}f}"


def proportion_ci(successes: int, n: int) -> Estimate:
    """Wald 95% CI for a proportion."""
    p = successes / n
    return Estimate(p, Z95 * math.sqrt(p * (1 - p) / n), n)


def mean_ci(values: list[float]) -> Estimate:
    """95% CI for a mean, from the standard error."""
    n = len(values)
    mean = statistics.fmean(values)
    return Estimate(mean, Z95 * statistics.stdev(values) / math.sqrt(n), n)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def simulate(
    board: Board, rules: GameRules, seed: int, n_games: int = N_GAMES
) -> list[GameResult]:
    """Runs one scenario and returns its raw results."""
    return ExperimentRunner(board, rules, seed).run(n_games)


def p1_win_rate(results: list[GameResult]) -> Estimate:
    """Share of games won by player 1."""
    return proportion_ci(sum(r.winner_index == 0 for r in results), len(results))


def per_player(results: list[GameResult], attribute: str) -> list[Estimate]:
    """Mean of a per-player tuple, one Estimate per player."""
    n_players = results[0].n_players
    return [
        mean_ci([getattr(r, attribute)[i] for r in results])
        for i in range(n_players)
    ]


# --------------------------------------------------------------------------- #
# Question 1 -- probability that the starting player wins
# --------------------------------------------------------------------------- #


def answer_q1(board: Board, n_games: int = N_GAMES) -> dict:
    """P(player 1 wins) in a fair two-player game.

    Players never interact, so the game is two independent solo races and
    player 1 wins whenever he needs no more turns than player 2. By symmetry
    this gives P(win) = 0.5 + P(tie in turns) / 2, which is reported as a
    cross-check on the simulated value.
    """
    results = simulate(board, GameRules(), SEEDS["q1_baseline"], n_games)
    p1 = p1_win_rate(results)
    return {
        "p1_win_rate": p1,
        "implied_tie_prob": 2 * (p1.value - 0.5),
        "results": results,
    }


# --------------------------------------------------------------------------- #
# Question 2 -- snakes per game
# --------------------------------------------------------------------------- #


def answer_q2(board: Board, n_games: int = N_GAMES) -> dict:
    """Average number of snakes players slide down per game.

    The per-player figures differ because the loser's race is truncated: the
    game stops on the winning roll, so the loser never finishes the board and
    meets fewer snakes than a solo player would. The solo run is included as
    the untruncated reference.
    """
    results = simulate(board, GameRules(), SEEDS["q2_snakes"], n_games)
    solo_rules = GameRules(start_positions=(1,), immunities=(0,))
    solo = simulate(board, solo_rules, SEEDS["solo_reference"], n_games)

    return {
        "total": mean_ci([r.total_snakes for r in results]),
        "by_player": per_player(results, "snakes_per_player"),
        "solo_reference": mean_ci([r.total_snakes for r in solo]),
        "results": results,
    }


# --------------------------------------------------------------------------- #
# Question 3 -- rolls per game when ladders work half the time
# --------------------------------------------------------------------------- #


def answer_q3(board: Board, n_games: int = N_GAMES) -> dict:
    """Average number of die rolls to complete a game when each ladder has a
    50% chance of working.

    Headline metric is the total across both players. The baseline (ladders
    always work) is included to size the effect.
    """
    rules = GameRules(ladder_success_prob=0.5)
    results = simulate(board, rules, SEEDS["q3_ladder_50"], n_games)
    baseline = simulate(board, GameRules(), SEEDS["q1_baseline"], n_games)

    total = mean_ci([r.total_rolls for r in results])
    base_total = mean_ci([r.total_rolls for r in baseline])
    return {
        "total_rolls": total,
        "by_player": per_player(results, "rolls_per_player"),
        "baseline_total_rolls": base_total,
        "increase_pct": 100 * (total.value / base_total.value - 1),
        "results": results,
    }


# --------------------------------------------------------------------------- #
# Question 4 -- starting square that balances the game
# --------------------------------------------------------------------------- #


def answer_q4(
    board: Board,
    n_games: int = N_GAMES,
    stop_margin: float = 0.05,
    patience: int = 4,
) -> dict:
    """Finds the starting square for player 2 that balances the odds.

    Squares are tested one at a time, from square 1 upwards. Once player 1's
    win rate drops below `0.5 - stop_margin`, the sweep continues for
    `patience` more squares before stopping, then picks the square whose win
    rate is closest to 50%.

    The patience buffer exists because the curve is not monotonic: snake heads
    (12, 14, 17) are bad starting squares and ladder bases (3, 5, 15, 18, 21)
    are worth more than their number suggests, so stopping at the first
    crossing could skip a better square just ahead.

    Note: a starting square is not "landed on", so a player starting on a
    ladder base does not climb it.
    """
    sweep: list[tuple[int, Estimate]] = []
    squares_after_crossing = 0

    for square in range(1, board.size):
        rules = GameRules(start_positions=(1, square))
        # Composite seeds make "4001:i" and "4002:i" disjoint streams, so
        # adjacent squares never share games despite adjacent base seeds.
        results = simulate(
            board, rules, SEEDS["q4_start_sweep"] + square, n_games
        )
        estimate = p1_win_rate(results)
        sweep.append((square, estimate))

        if estimate.value < 0.5 - stop_margin:
            squares_after_crossing += 1
            if squares_after_crossing >= patience:
                break

    best_square, best_estimate = min(sweep, key=lambda s: abs(s[1].value - 0.5))
    ties = [sq for sq, e in sweep if abs(e.value - 0.5) <= e.half_width]
    return {
        "best_square": best_square,
        "best_estimate": best_estimate,
        "sweep": sweep,
        "statistical_ties": ties,
    }


# --------------------------------------------------------------------------- #
# Question 5 -- immunity to the first snake
# --------------------------------------------------------------------------- #


def answer_q5(board: Board, n_games: int = N_GAMES) -> dict:
    """P(player 1 wins) when player 2 is immune to the first snake he meets."""
    rules = GameRules(immunities=(0, 1))
    results = simulate(board, rules, SEEDS["q5_immunity"], n_games)
    baseline = simulate(board, GameRules(), SEEDS["q1_baseline"], n_games)

    p1 = p1_win_rate(results)
    base = p1_win_rate(baseline)
    return {
        "p1_win_rate": p1,
        "baseline_p1_win_rate": base,
        "shift_pp": 100 * (p1.value - base.value),
        "results": results,
    }


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #


def main() -> None:
    board = Board.create_physa_test_board()
    line = "-" * 68

    print(f"\n{line}\nQUESTION 1 -- Does the starting player have an edge?\n{line}")
    q1 = answer_q1(board)
    print(f"P(player 1 wins) = {q1['p1_win_rate'].as_percent()}")
    print(f"  implies P(tie in turns) = {q1['implied_tie_prob']:.1%}")
    check = answer_q1(board, N_GAMES_CHECK)["p1_win_rate"]
    print(f"  convergence check ({N_GAMES_CHECK:,} games): {check.as_percent()}")

    print(f"\n{line}\nQUESTION 2 -- Snakes per game\n{line}")
    q2 = answer_q2(board)
    print(f"Snakes per game (both players) = {q2['total'].as_number()}")
    for i, e in enumerate(q2["by_player"]):
        print(f"  player {i + 1}: {e.as_number()}")
    print(f"  solo reference (full race, no truncation): {q2['solo_reference'].as_number()}")

    print(f"\n{line}\nQUESTION 3 -- Rolls per game with 50% ladders\n{line}")
    q3 = answer_q3(board)
    print(f"Rolls per game (both players) = {q3['total_rolls'].as_number()}")
    for i, e in enumerate(q3["by_player"]):
        print(f"  player {i + 1}: {e.as_number()}")
    print(f"  baseline (ladders always work): {q3['baseline_total_rolls'].as_number()}")
    print(f"  effect: {q3['increase_pct']:+.1f}% longer")

    print(f"\n{line}\nQUESTION 4 -- Balancing starting square for player 2\n{line}")
    q4 = answer_q4(board)
    for square, e in q4["sweep"]:
        mark = " <-- best" if square == q4["best_square"] else ""
        print(f"  P2 starts on {square:>2}: P(P1 wins) = {e.as_percent()}{mark}")
    print(f"\nBest square = {q4['best_square']} ({q4['best_estimate'].as_percent()})")
    print(f"  statistically tied with 50%: {q4['statistical_ties']}")

    print(f"\n{line}\nQUESTION 5 -- Player 2 immune to the first snake\n{line}")
    q5 = answer_q5(board)
    print(f"P(player 1 wins) = {q5['p1_win_rate'].as_percent()}")
    print(f"  baseline: {q5['baseline_p1_win_rate'].as_percent()}")
    print(f"  effect: {q5['shift_pp']:+.1f} percentage points")


if __name__ == "__main__":
    main()