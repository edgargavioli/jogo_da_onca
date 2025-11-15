import math, random
from movimentos import gerar_movimentos, aplicar_movimento, find_all_pieces_local, get_cell, pos_valida
from avaliacao import avaliar, analisar_vulnerabilidade_diagonal
from utils import board_to_key

def minimax(board, prof, maximizando, alpha=-math.inf, beta=math.inf, path_history=None):
    if path_history is None:
        path_history = []
    current_key = board_to_key(board)
    if path_history.count(current_key) >= 2:
        return (-50000 if maximizando else 50000), None
    from utils import count_pieces
    onca, cachorros = count_pieces(board, pos_valida, get_cell)
    if cachorros <= 5:
        return 50000, None
    if onca == 0:
        return -50000, None
    if not gerar_movimentos(board, 'o'):
        return -50000, None
    if prof == 0:
        return avaliar(board, 'o' if maximizando else 'c'), None
    new_path = path_history + [current_key]
    if maximizando:
        melhor_val = -math.inf
        melhor_mov = None
        moves = gerar_movimentos(board, 'o')
        saltos = [m for m in moves if len(m) == 3 and m[2] == 'salto_consecutivo']
        normais = [m for m in moves if not (len(m) == 3 and m[2] == 'salto_consecutivo')]
        random.shuffle(saltos)
        random.shuffle(normais)
        moves = saltos + normais
        for mov in moves:
            nb = aplicar_movimento(board, mov)
            val, _ = minimax(nb, prof - 1, False, alpha, beta, new_path)
            if val > melhor_val:
                melhor_val = val
                melhor_mov = mov
            alpha = max(alpha, val)
            if beta <= alpha:
                break
        return melhor_val, melhor_mov
    else:
        melhor_val = math.inf
        melhor_mov = None
        moves = gerar_movimentos(board, 'c')
        if not moves:
            return 50000, None
        def avaliar_seguranca_movimento(mov):
            (l1, c1), (l2, c2), _ = mov
            nb = aplicar_movimento(board, mov)
            nb_key = board_to_key(nb)
            repeticoes = new_path.count(nb_key)
            onca_pos = find_all_pieces_local(nb, 'o')
            if onca_pos:
                risco_diag, diagonais_exp, protecao_ok = analisar_vulnerabilidade_diagonal(
                    nb, l2, c2, onca_pos[0]
                )
            else:
                risco_diag, diagonais_exp, protecao_ok = 0, [], True
            risco_diagonal_normalizado = len(diagonais_exp) + (0 if protecao_ok else 2)
            vulnerabilidade_diagonal = risco_diag / 100.0
            onca_moves_after = gerar_movimentos(nb, 'o')
            em_risco_imediato = False
            em_risco_diagonal_imediato = False
            capturas_possiveis = 0
            for m in onca_moves_after:
                if len(m) == 3 and m[2] == 'salto_consecutivo':
                    caminho = m[0]
                    for i in range(len(caminho) - 1):
                        ml = (caminho[i][0] + caminho[i+1][0]) // 2
                        mc = (caminho[i][1] + caminho[i+1][1]) // 2
                        if (ml, mc) == (l2, c2):
                            em_risco_imediato = True
                            capturas_possiveis += 1
                            if abs(caminho[i][0] - caminho[i+1][0]) == 2 and \
                               abs(caminho[i][1] - caminho[i+1][1]) == 2:
                                em_risco_diagonal_imediato = True
                            break
                elif m[2] == (l2, c2):
                    em_risco_imediato = True
                    capturas_possiveis += 1
                    break
            suporte_total = 0
            suporte_diagonal = 0
            for dl, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                nl, nc = l2 + dl, c2 + dc
                if pos_valida(nl, nc) and get_cell(nb, nl, nc) == 'c':
                    suporte_total += 1
            for dl, dc in [(-1,-1), (-1,1), (1,-1), (1,1)]:
                nl, nc = l2 + dl, c2 + dc
                if pos_valida(nl, nc) and get_cell(nb, nl, nc) == 'c':
                    suporte_total += 1
                    suporte_diagonal += 1
            movimento_para_tras = 1 if l2 < l1 else 0
            bonus_linha = 0
            if l2 in [3, 4]:
                bonus_linha = -1
            isolamento = 1 if suporte_total == 0 else 0
            dogs_positions = find_all_pieces_local(nb, 'c')
            if dogs_positions:
                avg_l = sum(dl for dl, dc in dogs_positions) / len(dogs_positions)
                avg_c = sum(dc for dl, dc in dogs_positions) / len(dogs_positions)
                dist_centro_grupo = abs(l2 - avg_l) + abs(c2 - avg_c)
            else:
                dist_centro_grupo = 0
            cadeia_diagonal = suporte_diagonal >= 2
            noise = random.random() * 0.01
            return (
                repeticoes * 1000,
                em_risco_diagonal_imediato * 900,
                em_risco_imediato * 800,
                capturas_possiveis * 700,
                risco_diagonal_normalizado * 600,
                vulnerabilidade_diagonal,
                -suporte_diagonal * 50,
                -suporte_total * 30,
                isolamento * 400,
                movimento_para_tras * 200,
                dist_centro_grupo * 10,
                -cadeia_diagonal * 100,
                bonus_linha,
                noise
            )
        moves.sort(key=avaliar_seguranca_movimento)
        for mov in moves:
            nb = aplicar_movimento(board, mov)
            val, _ = minimax(nb, prof - 1, True, alpha, beta, new_path)
            if val < melhor_val:
                melhor_val = val
                melhor_mov = mov
            beta = min(beta, val)
            if beta <= alpha:
                break
        if melhor_mov is None and moves:
            melhor_mov = moves[0]
        return melhor_val, melhor_mov

def format_move(mov, lado):
    if len(mov) == 3 and mov[2] == 'salto_consecutivo':
        caminho = mov[0]
        num_saltos = len(caminho) - 1
        cmd = f"{lado} s {num_saltos}"
        for pos in caminho:
            cmd += f" {pos[0]} {pos[1]}"
        cmd += "\n"
        return cmd
    else:
        (l1, c1), (l2, c2), captura = mov
        if captura:
            return f"{lado} s 1 {l1} {c1} {l2} {c2}\n"
        else:
            return f"{lado} m {l1} {c1} {l2} {c2}\n"
