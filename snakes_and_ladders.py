"""Snakes and Ladders Monte Carlo simulation -- Physa technical case.

Assumptions
-----------
- 6x6 serpentine board, squares 1..36. Both players start on square 1.
- A player wins on `position >= 36`, checked right after the die move.
- No cascading: the landing square transports once, and that is final.
  The win check is re-run after a ladder, since a ladder may reach the end.
- `snakes_hit` counts snakes actually slid down; immunity does not count.
- Players never interact: two parallel solo races, first to finish wins.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

# One base seed per scenario, deliberately distinct: the scenarios consume
# randomness at different points, so sharing streams buys nothing.
SEEDS: dict[str, int] = {
    "q1_baseline": 1000,
    "q2_snakes": 2000,
    "q3_ladder_50": 3000,
    "q4_start_sweep": 4000,
    "q5_immunity": 5000,
    "solo_reference": 9000,
}


@dataclass(frozen=True)
class Board:
    """Static map of the game: size, snake heads and ladder bases."""

    size: int
    snakes: dict[int, int]
    ladders: dict[int, int]

    @classmethod
    def create_physa_test_board(cls) -> Board:
        """Builds the board given in the assignment."""
        return cls(
            size=36,
            ladders={3: 16, 5: 7, 15: 25, 18: 20, 21: 32},
            snakes={12: 2, 14: 11, 17: 4, 31: 19, 35: 22},
        )


@dataclass(frozen=True)
class GameRules:
    """Scenario configuration. Each question is one instance of this class.

    Q1/Q2: GameRules()                     Q4: GameRules(start_positions=(1, k))
    Q3:    GameRules(ladder_success_prob=0.5)
    Q5:    GameRules(immunities=(0, 1))    solo: start_positions=(1,), immunities=(0,)
    """

    start_positions: tuple[int, ...] = (1, 1)
    ladder_success_prob: float = 1.0
    immunities: tuple[int, ...] = (0, 0)
    dice_sides: int = 6

    def __post_init__(self) -> None:
        if len(self.start_positions) != len(self.immunities):
            raise ValueError(
                "start_positions and immunities must have the same length "
                f"(got {len(self.start_positions)} and {len(self.immunities)})."
            )

    @property
    def n_players(self) -> int:
        return len(self.start_positions)


class Player:
    """Mutable state of one player during a single game."""

    def __init__(self, name: str, start_position: int, immunities: int) -> None:
        self.name = name
        self.start_position = start_position
        self.initial_immunities = immunities
        self.reset()

    def reset(self) -> None:
        """Restores the starting state, so one object can play many games."""
        self.position = self.start_position
        self.dice_rolls = 0
        self.snakes_hit = 0
        self.ladders_climbed = 0
        self.immunities_left = self.initial_immunities


@dataclass(frozen=True)
class GameResult:
    """Immutable summary of one finished game."""

    winner_index: int
    total_rolls: int
    rolls_per_player: tuple[int, ...]
    snakes_per_player: tuple[int, ...]
    ladders_per_player: tuple[int, ...]

    @property
    def n_players(self) -> int:
        return len(self.rolls_per_player)

    @property
    def total_snakes(self) -> int:
        return sum(self.snakes_per_player)

    @property
    def total_ladders(self) -> int:
        return sum(self.ladders_per_player)

    def check_turn_order_invariant(self) -> None:
        """Roll number r always belongs to player (r-1) % N, and the game stops
        on the winning roll -- so total_rolls alone determines the winner."""
        expected = (self.total_rolls - 1) % self.n_players
        assert expected == self.winner_index, (
            f"Turn-order invariant violated: total_rolls={self.total_rolls}, "
            f"expected winner {expected}, got {self.winner_index}."
        )


class GameEngine:
    """Applies the rules and runs games to completion.

    Owns its random source instead of the `random` module globals, so results
    do not depend on execution order and any game can be reproduced by seed.
    """

    def __init__(
        self, board: Board, rules: GameRules, rng: random.Random | None = None
    ) -> None:
        self.board = board
        self.rules = rules
        self.rng = rng if rng is not None else random.Random()
        self.players = [
            Player(f"Player {i + 1}", start, immunity)
            for i, (start, immunity) in enumerate(
                zip(rules.start_positions, rules.immunities)
            )
        ]

    def play_full_game(self, verbose: bool = False) -> GameResult:
        """Resets state, plays one game and returns its summary."""
        for player in self.players:
            player.reset()

        # Termination is guaranteed: every roll advances at least one square
        # and every snake lands on a square from which the end is reachable.
        while True:
            for index, player in enumerate(self.players):
                if self._play_turn(player, verbose):
                    return GameResult(
                        winner_index=index,
                        total_rolls=sum(p.dice_rolls for p in self.players),
                        rolls_per_player=tuple(p.dice_rolls for p in self.players),
                        snakes_per_player=tuple(p.snakes_hit for p in self.players),
                        ladders_per_player=tuple(
                            p.ladders_climbed for p in self.players
                        ),
                    )

    def _play_turn(self, player: Player, verbose: bool) -> bool:
        """Plays one turn. Returns True if the player won."""
        origin = player.position
        roll = self.rng.randint(1, self.rules.dice_sides)
        player.dice_rolls += 1
        player.position += roll

        if verbose:
            print(f"[{player.name}] {origin} + {roll} -> {player.position}")

        if player.position >= self.board.size:
            if verbose:
                print(f"    WIN -- {player.name} reached the end.")
            return True

        # A square is either a ladder base or a snake head, never both:
        # the elif makes a ladder-into-snake cascade impossible by construction.
        ladder = self.board.ladders.get(player.position)
        snake = self.board.snakes.get(player.position)

        if ladder is not None:
            # random() is in [0, 1), so prob 1.0 always succeeds.
            if self.rng.random() < self.rules.ladder_success_prob:
                if verbose:
                    print(f"    LADDER -- {player.position} -> {ladder}")
                player.position = ladder
                player.ladders_climbed += 1
                if player.position >= self.board.size:
                    if verbose:
                        print(f"    WIN -- {player.name} reached the end.")
                    return True
            elif verbose:
                print(f"    LADDER FAILED -- stays on {player.position}")

        elif snake is not None:
            if player.immunities_left > 0:
                player.immunities_left -= 1
                if verbose:
                    print(f"    IMMUNITY -- snake on {player.position} ignored")
            else:
                if verbose:
                    print(f"    SNAKE -- {player.position} -> {snake}")
                player.position = snake
                player.snakes_hit += 1

        return False


class ExperimentRunner:
    """Runs a scenario N times, each game with its own stream derived from
    `seed`, so results never depend on execution order.

    If `seed` is omitted, one is drawn at random and stored in `self.seed`:
    the run is random, but still reproducible after the fact by passing that
    value back in.
    """

    def __init__(
        self, board: Board, rules: GameRules, seed: int | None = None
    ) -> None:
        self.board = board
        self.rules = rules
        self.seed = seed if seed is not None else random.Random().randrange(2**32)

    def run(self, n_games: int, validate: bool = True) -> list[GameResult]:
        """Simulates n_games independent games."""
        results = []
        for i in range(n_games):
            # Composite seed rather than `seed + i`, so the seed ranges of two
            # scenarios can never overlap and share games.
            rng = random.Random(f"{self.seed}:{i}")
            result = GameEngine(self.board, self.rules, rng).play_full_game()
            if validate:
                result.check_turn_order_invariant()
            results.append(result)
        return results

    @staticmethod
    def to_dataframe(results: list[GameResult]):
        """Converts results into a DataFrame, one row per game.

        pandas is imported here so the simulation core stays dependency-free.
        """
        import pandas as pd

        rows = []
        for i, r in enumerate(results):
            row = {
                "game_index": i,
                "winner_index": r.winner_index,
                "total_rolls": r.total_rolls,
                "total_snakes": r.total_snakes,
                "total_ladders": r.total_ladders,
            }
            for p in range(r.n_players):
                row[f"p{p + 1}_rolls"] = r.rolls_per_player[p]
                row[f"p{p + 1}_snakes"] = r.snakes_per_player[p]
                row[f"p{p + 1}_ladders"] = r.ladders_per_player[p]
            rows.append(row)
        return pd.DataFrame(rows)


if __name__ == "__main__":
    board = Board.create_physa_test_board()

    # One narrated game as a visual check that the rules behave correctly.
    GameEngine(board, GameRules(), rng=random.Random(7)).play_full_game(verbose=True)

    # Baseline smoke test. Omit the seed for a random run: the drawn seed is
    # kept in runner.seed, so the run stays reproducible after the fact.
    runner = ExperimentRunner(board, GameRules(), SEEDS["q1_baseline"])
    results = runner.run(10_000)
    n = len(results)
    print(f"\n--- baseline, 10,000 games (seed={runner.seed}) ---")
    print(f"P(Player 1 wins) : {sum(r.winner_index == 0 for r in results) / n:.4f}")
    print(f"mean total rolls : {sum(r.total_rolls for r in results) / n:.4f}")
    print(f"mean total snakes: {sum(r.total_snakes for r in results) / n:.4f}")