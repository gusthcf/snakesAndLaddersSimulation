# Snakes and Ladders

---

## Respostas

| # | Pergunta | Resposta |
|---|---|---|
| **1** | Probabilidade de o primeiro jogador vencer | **52,9% ± 1,0 p.p.** |
| **2** | Cobras por jogo (ambos os jogadores) | **3,11 ± 0,05** (J1: 1,60 · J2: 1,51) |
| **3** | Lançamentos por jogo com escadas a 50% | **22,46 ± 0,18** (+18,6% vs. base) |
| **4** | Casa inicial do Jogador 2 para equilibrar | **Casa 7** → P(J1) = 49,7% ± 0,3 p.p. |
| **5** | P(J1) com imunidade à primeira cobra do J2 | **38,2% ± 1,0 p.p.** |

Todos os valores acompanham intervalo de confiança de 95%. A análise completa, com gráficos e raciocínio, está em `analysis.ipynb`.

---

## Estrutura

| Arquivo | Papel |
|---|---|
| `snakes_and_ladders.py` | Motor de simulação — apenas biblioteca padrão |
| `analysis.py` | Agregação, intervalos de confiança e as cinco respostas |
| `analysis.ipynb` | Notebook com gráficos e narrativa |
| `analysis.html` | O notebook exportado, para leitura sem executar nada |
| `board.jpg` | Imagem representando o tabuleiro |

As dependências apontam para dentro: o motor não conhece a camada de análise, e a análise não conhece as engrenagens do motor. O núcleo roda sem pandas.

### Arquitetura do motor

| Classe | Responsabilidade |
|---|---|
| `Board` | Mapa estático: tamanho, cobras e escadas |
| `GameRules` | Configuração de cenário — cada pergunta é uma instância |
| `Player` | Estado mutável de um jogador durante uma partida |
| `GameResult` | Resumo imutável de uma partida encerrada |
| `GameEngine` | Aplica as regras e conduz a partida |
| `ExperimentRunner` | Executa N partidas, controla sementes, converte para DataFrame |

Os cinco cenários são configuração, não código:

```python
GameRules()                              # Q1, Q2
GameRules(ladder_success_prob=0.5)       # Q3
GameRules(start_positions=(1, 7))        # Q4
GameRules(immunities=(0, 1))             # Q5
GameRules(start_positions=(1,), immunities=(0,))   # corrida solo de referência
```

---

## Como executar

```bash
pip install pandas matplotlib jupyter
python analysis.py          # imprime as cinco respostas no terminal
jupyter notebook            # abre o notebook com os gráficos
```

O motor sozinho não precisa de dependências externas:

```bash
python snakes_and_ladders.py
```

---

## Premissas

- Tabuleiro 6×6 serpenteante, casas 1 a 36. Ambos começam na casa 1.
- Escadas `{3: 16, 5: 7, 15: 25, 18: 20, 21: 32}`, cobras `{12: 2, 14: 11, 17: 4, 31: 19, 35: 22}`.
- Vitória ao **atingir ou ultrapassar** a casa 36, verificada logo após o lançamento do dado.
- **Sem encadeamento**: a casa em que se cai transporta uma única vez.
- A casa inicial **não é "pisada"** — quem começa na base de uma escada não sobe por ela.
- Os jogadores não interagem: são duas corridas solo paralelas.
- "Lançamentos para completar um jogo" (Pergunta 3) é o total somando os dois jogadores. A leitura por jogador está reportada como sensibilidade.

---

## Método

**Precisão.** As 10.000 simulações pedidas entregam ±1,0 p.p. em probabilidades — suficiente para quatro das cinco perguntas. A Pergunta 4 é a exceção: ela compara casas separadas por menos de 1 p.p., e nessa resolução o ranking seria ruído. Por isso ela usa duas etapas, varredura com 10.000 e refino das finalistas com 100.000. A varredura sozinha teria apontado a casa 8, que é a resposta errada.

**Reprodutibilidade.** Cada cenário tem semente base própria, registrada em `SEEDS`, e cada partida deriva sua própria sequência a partir dela. As sementes são compostas como texto (`"4000:17"`) em vez de somadas, garantindo que os espaços de aleatoriedade de dois cenários sejam disjuntos por construção.

**Limitações.** As respostas assumem dado justo de 6 lados, ausência de interação entre jogadores e o tabuleiro exatamente como lido da imagem do enunciado — a única entrada não verificável do modelo.
