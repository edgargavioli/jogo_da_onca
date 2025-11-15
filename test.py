import ctypes
import argparse
import math
import copy
from collections import deque

# Carrega a biblioteca compartilhada
lib = ctypes.CDLL("./libtabuleiro.so")

lib.tabuleiro_conecta.argtypes = (ctypes.c_int, ctypes.POINTER(ctypes.c_char_p))
lib.tabuleiro_conecta.restype = None
lib.tabuleiro_envia.argtypes = (ctypes.c_char_p,)
lib.tabuleiro_envia.restype = None
lib.tabuleiro_recebe.argtypes = (ctypes.c_char_p,)
lib.tabuleiro_recebe.restype = None

BUF_SIZE = 2048
MAX_PROF = 4  # profundidade do minimax

# quantos estados recentes armazenar (ajuste se quiser)
RECENT_STATES_MAX = 8
RECENT_BOARDS = deque(maxlen=RECENT_STATES_MAX)

# --- PARSEAMENTO DO TABULEIRO ---

def detect_front_dir(board):
    """
    Retorna +1 se os cachorros estiverem no topo (logo devem mover para increasing i),
    retorna -1 se os cachorros estiverem no fundo (devem mover para decreasing i).
    Heurística: calcula índice médio das posições 'c' e compara com centro.
    """
    rows = len(board)
    center_row = rows // 2
    sum_r = 0
    n = 0
    for i, row in enumerate(board):
        for j, ch in enumerate(row):
            if ch == 'c':
                sum_r += i
                n += 1
    if n == 0:
        return 1
    avg = sum_r / n
    return 1 if avg < center_row else -1


def board_to_key(board):
    """Converte board (lista de linhas com '#') em uma string compacta que representa o estado relevante."""
    # remove bordas e quebras; mantém apenas os caracteres relevantes por linha
    rows = []
    for row in board:
        # filtra somente os caracteres do campo interior (inclui - o c e espaços)
        filtered = ''.join(ch for ch in row if ch in ('-', 'o', 'c'))
        if filtered:
            rows.append(filtered)
    return "|".join(rows)

def mov_possivel_python(tipo, lo, co, ld, cd):
    # ESPAÇOS válidos l:1..7 c:1..5 (mesma convenção do controlador C)
    def abs_(x): return -x if x < 0 else x

    # valida limites
    if lo < 1 or lo > 7 or co < 1 or co > 5:
        return False
    if ld < 1 or ld > 7 or cd < 1 or cd > 5:
        return False

    distl = abs_(lo - ld)
    distc = abs_(co - cd)
    if (distl + distc) == 0:
        return False

    if tipo == 'm':
        # casos especiais do C
        if (lo == 7) and (distl == 0):
            if distc == 2:
                return True
            else:
                return False
        if (distl > 1) or (distc > 1):
            return False
        if ((lo + co) % 2) and ((distl + distc) > 1):
            return False
        if (lo == 5) and (ld == 6) and (co != 3):
            return False
        if (lo == 6) and ((co % 2) == 0):
            if (ld == 5) and (cd != 3):
                return False
            if (ld == 7) and (cd == 3):
                return False
        return True

    if tipo == 's':
        if (lo == 7) and (distl == 0):
            if distc == 4:
                return True
            else:
                return False
        if (distl == 1) or (distc == 1) or (distl + distc) > 4:
            return False
        if ((lo + co) % 2) and ((distl + distc) > 2):
            return False
        if (lo == 5) and (ld == 7) and (co != 3):
            return False
        if (lo == 6) and (ld == 4) and (
            ((co == 2) and (cd != 4)) or ((co == 4) and (cd != 2))
        ):
            return False
        if (lo == 7) and (cd != 3):
            return False
        return True

    return False


def parse_board_from_server(msg: str):
    """Extrai o tabuleiro ASCII do servidor."""
    lines = [l for l in msg.splitlines() if l.strip()]
    board_lines = [l for l in lines if l.startswith("#")]
    if not board_lines:
        return None
    board = [list(line) for line in board_lines]
    return board


def find_piece(board, piece):
    for i, row in enumerate(board):
        for j, c in enumerate(row):
            if c == piece:
                return (i, j)
    return None


def count_pieces(board):
    onca = sum(row.count("o") for row in board)
    cachorros = sum(row.count("c") for row in board)
    return onca, cachorros


# --- TOPOLOGIA ---

def vizinhos_validos(board, i, j):
    """Retorna apenas os vizinhos ortogonais válidos."""
    dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    viz = []
    for di, dj in dirs:
        ni, nj = i + di, j + dj
        if 0 <= ni < len(board) and 0 <= nj < len(board[0]):
            if board[ni][nj] in ['-', 'o', 'c']:
                viz.append((ni, nj))
    return viz

# --- MOVIMENTOS ---

def gerar_movimentos(board, lado):
    moves = []
    rows = len(board)
    cols = len(board[0])

    # detecta direção "pra frente" dos cachorros
    front_dir = detect_front_dir(board)  # +1 ou -1

    for i in range(1, rows - 1):
        for j in range(1, cols - 1):
            p = board[i][j]
            if p != lado:
                continue

            for di, dj in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
                ni, nj = i + di, j + dj
                if not (0 <= ni < rows and 0 <= nj < cols):
                    continue
                destino = board[ni][nj]

                # MOVIMENTO SIMPLES -----------------------------------
                if destino == '-':
                    lo, co, ld, cd = i, j, ni, nj

                    if lado == 'c':
                        # Cachorro só anda pra frente (front_dir) ou lateralmente (dj != 0)
                        # proibir recuar: di * front_dir < 0 significa mover contra frente
                        if di * front_dir < 0:
                            continue
                        # sem diagonais para cachorro
                        if abs(di) == 1 and abs(dj) == 1:
                            continue
                        # não considera espaços "fora" do tabuleiro (caractere espaço)
                        if board[ni][nj] == ' ':
                            continue

                    if mov_possivel_python('m', lo, co, ld, cd):
                        moves.append(((i, j), (ni, nj), None))

                # CAPTURA (apenas onça) -------------------------------
                elif lado == 'o' and destino == 'c':
                    di2, dj2 = ni - i, nj - j
                    ci, cj = ni + di2, nj + dj2

                    # bordas e espaços inválidos
                    if not (0 <= ci < rows and 0 <= cj < cols):
                        continue
                    if board[ci][cj] != '-':
                        continue

                    lo, co, ld, cd = i, j, ci, cj
                    if mov_possivel_python('s', lo, co, ld, cd):
                        moves.append(((i, j), (ci, cj), (ni, nj)))

    # remove duplicatas e movimentos nulos
    unique = {}
    for m in moves:
        key = (m[0], m[1], m[2])
        unique[key] = m
    moves = [m for m in unique.values() if m[0] != m[1]]
    return moves

def aplicar_movimento(board, mov):
    (i1, j1), (i2, j2), captura = mov
    b2 = copy.deepcopy(board)
    b2[i2][j2] = b2[i1][j1]
    b2[i1][j1] = '-'
    if captura:
        ci, cj = captura
        b2[ci][cj] = '-'
    return b2


def jogo_terminou(board):
    onca, cachorros = count_pieces(board)
    if onca == 0:
        return True
    if gerar_movimentos(board, 'o') == []:
        return True
    if cachorros == 0:
        return True
    return False


def avaliar(board, lado_atual='o'):
    """
    Heurística adaptativa que considera:
      - Capturas (principal fator).
      - Mobilidade da onça e dos cachorros.
      - Pressão sobre a onça (cachorros próximos).
      - Centralidade e segurança da onça.
      - Repetição de estado (penalização forte).
      - Situação de quase-cercamento progressivo.
    """

    # pesos principais
    W_CAPTURE = 1200
    W_ONCA_MOB = 7
    W_DOG_MOB = -4
    W_ADJ_DOG = -80
    W_DIST_MEAN = 10
    W_CENTER = 4
    W_REPEAT = -1500
    W_BLOCK = 400
    W_SAFE_DOGS = -2  # cães seguros (não ameaçados pela onça) valem mais para os cachorros

    onca, cachorros = count_pieces(board)
    captured = max(0, 14 - cachorros)

    # posições
    onca_pos = find_piece(board, 'o')
    if not onca_pos:
        # onça capturada = derrota
        return -99999 if lado_atual == 'o' else 99999

    oi, oj = onca_pos

    # --- Mobilidade ---
    onca_moves = gerar_movimentos(board, 'o')
    dog_moves = gerar_movimentos(board, 'c')
    mobilidade_onca = len(onca_moves)
    mobilidade_dogs = len(dog_moves)

    # --- Cachorros adjacentes e distância média ---
    adj_dogs = 0
    total_dist = 0
    ndogs = 0
    dogs_seguro = 0

    for i, row in enumerate(board):
        for j, ch in enumerate(row):
            if ch == 'c':
                d = abs(i - oi) + abs(j - oj)
                total_dist += d
                ndogs += 1
                # cachorro adjacente?
                if abs(i - oi) <= 1 and abs(j - oj) <= 1 and not (i == oi and j == oj):
                    adj_dogs += 1

                # cachorro seguro (não pode ser capturado no próximo turno)
                pode_ser_capturado = False
                for di, dj in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
                    ni, nj = i - di, j - dj
                    ci, cj = i + di, j + dj
                    if (
                        0 <= ni < len(board)
                        and 0 <= nj < len(board[0])
                        and 0 <= ci < len(board)
                        and 0 <= cj < len(board[0])
                        and board[ni][nj] == 'o'
                        and board[ci][cj] == '-'
                    ):
                        pode_ser_capturado = True
                        break
                if not pode_ser_capturado:
                    dogs_seguro += 1

    mean_dist = total_dist / ndogs if ndogs else 10

    # --- Centralidade da onça ---
    center_i, center_j = 4, 3
    center_dist = abs(oi - center_i) + abs(oj - center_j)
    centrality = max(0, 6 - center_dist)

    # --- Cercamento progressivo ---
    # Mede se a onça está em região com poucas casas livres ao redor (pressão posicional)
    free_around = 0
    for di in range(-2, 3):
        for dj in range(-2, 3):
            ni, nj = oi + di, oj + dj
            if 0 <= ni < len(board) and 0 <= nj < len(board[0]):
                if board[ni][nj] == '-':
                    free_around += 1
    block_pressure = (9 - min(free_around, 9))  # 0..9 → mais bloqueio = valor maior

    # --- Repetição ---
    key = board_to_key(board)
    repeat_penalty = W_REPEAT if key in RECENT_BOARDS else 0

    # --- Composição de score ---
    score = 0
    score += captured * W_CAPTURE
    score += mobilidade_onca * W_ONCA_MOB
    score += (mobilidade_dogs / max(1, ndogs)) * W_DOG_MOB
    score += adj_dogs * W_ADJ_DOG
    score += mean_dist * W_DIST_MEAN
    score += centrality * W_CENTER
    score += block_pressure * W_BLOCK
    score += dogs_seguro * W_SAFE_DOGS
    score += repeat_penalty

    # --- Ajuste pelo lado da vez ---
    # Se for o turno dos cachorros, inverte o sinal da heurística (minimax usa valores simétricos)
    if lado_atual == 'c':
        score = -score

    return score

# --- MINIMAX ---

def minimax(board, prof, maximizando, alpha=-math.inf, beta=math.inf):
    if prof == 0 or jogo_terminou(board):
        return avaliar(board, 'o' if maximizando else 'c'), None

    if maximizando:  # onça
        melhor = -math.inf
        melhor_mov = None
        for mov in gerar_movimentos(board, 'o'):
            nb = aplicar_movimento(board, mov)
            val, _ = minimax(nb, prof - 1, False, alpha, beta)
            if val > melhor:
                melhor = val
                melhor_mov = mov
            alpha = max(alpha, val)
            if beta <= alpha:
                break
        return melhor, melhor_mov
    else:  # cachorro
        pior = math.inf
        melhor_mov = None
        for mov in gerar_movimentos(board, 'c'):
            nb = aplicar_movimento(board, mov)
            val, _ = minimax(nb, prof - 1, True, alpha, beta)
            if val < pior:
                pior = val
                melhor_mov = mov
            beta = min(beta, val)
            if beta <= alpha:
                break
        return pior, melhor_mov


def format_move(mov, lado):
    (i1, j1), (i2, j2), captura = mov
    # tipo "s" = salto (captura), "m" = movimento normal
    tipo = "s" if captura else "m"

    if tipo == "s":
        # para salto, há sempre 1 salto se captura não for None
        num_saltos = 1
        return f"{lado} s {num_saltos} {i1} {j1} {i2} {j2}\n"
    else:
        # movimento simples
        return f"{lado} m {i1} {j1} {i2} {j2}\n"


# --- LOOP PRINCIPAL ---

def parse_turn(msg):
    lines = [l.strip() for l in msg.splitlines() if l.strip()]
    if not lines:
        return None

    header = lines[0].split()
    if len(header) >= 1:
        return header[0]  # o primeiro caractere é o seu lado
    return None

def lado_da_vez(msg: str):
    lines = [l.strip() for l in msg.splitlines() if l.strip()]
    if len(lines) >= 2 and ' ' in lines[1]:
        partes = lines[1].split()
        return partes[0]  # 'c' ou 'o'
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("lado", choices=["o", "c"])
    parser.add_argument("-ip", default="127.0.0.1")
    parser.add_argument("-porta", default="10001")
    args = parser.parse_args()

    argv = [b"python", args.lado.encode(), args.ip.encode(), args.porta.encode()]
    c_argv = (ctypes.c_char_p * len(argv))(*argv)
    lib.tabuleiro_conecta(len(argv), c_argv)

    buf = ctypes.create_string_buffer(BUF_SIZE)

    while True:
        lib.tabuleiro_recebe(buf)
        msg = buf.value.decode(errors="ignore")
        if not msg:
            continue

        print(msg)
        board = parse_board_from_server(msg)
        turno = parse_turn(msg)

        if not board:
            continue

        if turno == args.lado:
            print(f"🔹 É minha vez ({args.lado})")
            _, mov = minimax(board, MAX_PROF, args.lado == 'o')
            if mov:
                # validação local antes de enviar
                (i1, j1), (i2, j2), captura = mov
                # origem e destino devem corresponder ao board atual
                orig_piece = board[i1][j1]
                dest_piece = board[i2][j2]
                if orig_piece != args.lado:
                    print("DEBUG: movimento rejeitado: origem não contém peça esperada:", mov, "orig_piece=", orig_piece)
                else:
                    # decide tipo e valida via mov_possivel_python (usando índices já no formato 1..7/1..5)
                    tipo = 's' if captura else 'm'
                    if tipo == 'm':
                        ok = mov_possivel_python('m', i1, j1, i2, j2)
                    else:
                        ok = mov_possivel_python('s', i1, j1, i2, j2)
                    if not ok:
                        print("DEBUG: movimento rejeitado por mov_possivel_python:", mov, "tipo=", tipo)
                    else:
                        cmd = format_move(mov, args.lado)
                        print(f"Movimento escolhido: {cmd.strip()}")
                        lib.tabuleiro_envia(cmd.encode())
                        # registra estado atual como recente (evita repetir)
                        k = board_to_key(board)
                        RECENT_BOARDS.append(k)
            else:
                print("Sem movimentos possíveis.")
                break

        # Entrada manual opcional
        else:
            linha = input("> ").strip()
            if linha == "0":
                break
            if linha:
                lib.tabuleiro_envia(linha.encode())
                # registra estado atual como recente (evita repetir)
                k = board_to_key(board)
                RECENT_BOARDS.append(k)

if __name__ == "__main__":
    main()
