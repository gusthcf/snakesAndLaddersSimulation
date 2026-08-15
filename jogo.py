import random
from typing import Dict, Optional

# --- 1. O TABULEIRO ---
class Board:
    def __init__(self, size: int, snakes: Dict[int, int], ladders: Dict[int, int]):
        self.size = size
        self.snakes = snakes
        self.ladders = ladders

    @classmethod
    def create_physa_test_board(cls) -> 'Board':
        board_size = 36
        ladders_config = {3: 16, 5: 7, 15: 25, 18: 20, 21: 32}
        snakes_config = {12: 2, 14: 11, 17: 4, 31: 19, 35: 22}
        return cls(size=board_size, snakes=snakes_config, ladders=ladders_config)

    def get_ladder_destination(self, position: int) -> Optional[int]:
        return self.ladders.get(position)

    def get_snake_destination(self, position: int) -> Optional[int]:
        return self.snakes.get(position)


# --- 2. O JOGADOR ---
class Player:
    def __init__(self, name: str, start_position: int = 1, immunities: int = 0):
        self.name = name
        self.position = start_position
        self.snakes_encountered = 0
        self.immunities = immunities
        self.dice_rolls = 0


# --- 3. O JUIZ (MOTOR DE SIMULAÇÃO) ---
class GameSimulation:
    def __init__(self, board: Board, players: list, ladder_chance: float = 1.0):
        self.board = board
        self.players = players
        self.ladder_chance = ladder_chance
        self.winner = None

    def roll_die(self) -> int:
        return random.randint(1, 6)

    def play_turn(self, player: Player, verbose: bool = False) -> bool:
        start_pos = player.position
        roll = self.roll_die()
        player.dice_rolls += 1
        player.position += roll
        
        if verbose:
            print(f"[{player.name}] Estava na casa {start_pos}, rolou {roll} e foi para a casa {player.position}.")

        # Verifica vitória antes de checar cobras/escadas
        if player.position >= self.board.size:
            if verbose:
                print(f"🏆 {player.name} alcançou a casa {player.position} e VENCEU O JOGO!")
            return True

        # Checa Escadas
        ladder_dest = self.board.get_ladder_destination(player.position)
        if ladder_dest is not None:
            if random.random() <= self.ladder_chance:
                if verbose:
                    print(f"   ⬆️  ESCALADA! {player.name} subiu pela escada da casa {player.position} para a {ladder_dest}.")
                player.position = ladder_dest
            else:
                if verbose:
                    print(f"   ❌ ESCALADA FALHOU! {player.name} tentou subir a escada na casa {player.position}, mas não conseguiu.")

        # Checa Cobras
        snake_dest = self.board.get_snake_destination(player.position)
        if snake_dest is not None:
            if player.immunities > 0:
                player.immunities -= 1
                if verbose:
                    print(f"   🛡️  IMUNIDADE! {player.name} parou na cabeça da cobra na casa {player.position}, mas usou imunidade e não caiu.")
            else:
                if verbose:
                    print(f"   🐍 COBRA! {player.name} caiu na cobra da casa {player.position} e escorregou para a {snake_dest}.")
                player.position = snake_dest
                player.snakes_encountered += 1

        if verbose:
            print(f"   📍 Fim do turno de {player.name}: Casa final = {player.position}\n")

        return False

    def play_full_game(self, verbose: bool = False) -> str:
        game_over = False
        
        if verbose:
            print("========================================")
            print("🏁 INICIANDO NOVA PARTIDA DE TESTE 🏁")
            print("========================================\n")

        while not game_over:
            for player in self.players:
                has_won = self.play_turn(player, verbose)
                if has_won:
                    self.winner = player.name
                    game_over = True
                    break
                    
        return self.winner


# --- 4. EXECUTANDO UMA ÚNICA PARTIDA COM LOGS ---
if __name__ == "__main__":
    # 1. Cria o tabuleiro da Physa
    meu_tabuleiro = Board.create_physa_test_board()
    
    # 2. Cria os dois jogadores começando na casa 1
    jogador1 = Player(name="Jogador 1", start_position=1)
    jogador2 = Player(name="Jogador 2", start_position=1)
    
    # 3. Cria o Juiz passando o tabuleiro e os jogadores
    juiz = GameSimulation(board=meu_tabuleiro, players=[jogador1, jogador2])
    
    # 4. Inicia o jogo com verbose=True para ver os prints
    vencedor = juiz.play_full_game(verbose=True)