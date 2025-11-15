import random
from movimentos import gerar_movimentos_onca, gerar_movimentos_cachorro, get_cell, pos_valida
from utils import board_to_key, find_all_pieces, count_pieces

def analisar_vulnerabilidade_diagonal(board, dl, dc, onca_pos):
    ol, oc = onca_pos
    risco_total = 0
    diagonais_expostas = []
    tem_protecao = {(-1, -1): False, (-1, 1): False, (1, -1): False, (1, 1): False}
    for dir_l, dir_c in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
        pouso_l, pouso_c = dl + dir_l, dc + dir_c
        onca_l, onca_c = dl - dir_l, dc - dir_c
        if not pos_valida(pouso_l, pouso_c) or not pos_valida(onca_l, onca_c):
            continue
        tem_espaco_pouso = get_cell(board, pouso_l, pouso_c) == '-'
        onca_pode_estar = get_cell(board, onca_l, onca_c) in ['-', 'o']
        if tem_espaco_pouso and onca_pode_estar:
            dist_onca = abs(ol - onca_l) + abs(oc - onca_c)
            cachorro_protegendo = get_cell(board, pouso_l, pouso_c) == 'c'
            cachorro_adj_diagonal = False
            for check_l, check_c in [(dl + dir_l, dc), (dl, dc + dir_c)]:
                if pos_valida(check_l, check_c) and get_cell(board, check_l, check_c) == 'c':
                    cachorro_adj_diagonal = True
                    break
            tem_protecao[(dir_l, dir_c)] = cachorro_protegendo or cachorro_adj_diagonal
            if not (cachorro_protegendo or cachorro_adj_diagonal):
                diagonais_expostas.append((dir_l, dir_c))
                if dist_onca == 0:
                    risco_total += 1000
                elif dist_onca <= 1:
                    risco_total += 500
                elif dist_onca <= 2:
                    risco_total += 200
                elif dist_onca <= 3:
                    risco_total += 50
    tem_protecao_adequada = sum(tem_protecao.values()) >= 2
    return risco_total, diagonais_expostas, tem_protecao_adequada

def avaliar(board, lado_atual):
    W_CAPTURE = 2000000
    W_ONCA_MOB = 25
    W_ONCA_CAPTURE = 150
    W_CENTER = 5
    W_DOG_SAFETY = -1500
    W_DOG_DIAGONAL_RISK = -2000
    W_DOG_DIAGONAL_EXPOSED = -1800
    W_DIAGONAL_VULNERABILITY = -1500
    W_DOG_FORMATION = -500
    W_ENCIRCLE = -200
    W_DOG_SUPPORT = -180
    W_DIAGONAL_SUPPORT = -400
    W_BLOCK_ESCAPE = -250
    W_DOG_ADVANCE = -8
    W_LINE_CONTROL = -150
    W_CENTER_CONTROL = -200
    W_WALL_FORMATION = -150
    W_PREVENT_RETREAT = -300
    W_DIAGONAL_CHAIN = -300
    W_REPEAT = -1000000
    W_RANDOMNESS = 20

    onca, cachorros = None, None
    onca, cachorros = count_pieces(board, pos_valida, get_cell)
    captured = 14 - cachorros

    onca_pos = find_all_pieces(board, 'o', pos_valida, get_cell)
    if not onca_pos:
        return -99999 if lado_atual == 'o' else 99999

    ol, oc = onca_pos[0]
    onca_moves = gerar_movimentos_onca(board)

    capturas_disponiveis = 0
    for m in onca_moves:
        if len(m) == 3 and m[2] == 'salto_consecutivo':
            caminho = m[0]
            capturas_disponiveis += len(caminho) - 1
        elif len(m) >=3 and m[2] is not None:
            capturas_disponiveis += 1

    dogs_positions = find_all_pieces(board, 'c', pos_valida, get_cell)
    dogs_at_risk = 0
    dogs_with_support = 0
    dogs_isolated = 0
    dogs_diagonal_risk = 0
    total_diagonal_vulnerability = 0
    diagonais_expostas_total = 0
    dogs_with_diagonal_protection = 0

    for dl, dc in dogs_positions:
        risco_diag, diagonais_exp, protecao_adequada = analisar_vulnerabilidade_diagonal(
            board, dl, dc, (ol, oc)
        )
        total_diagonal_vulnerability += risco_diag
        diagonais_expostas_total += len(diagonais_exp)
        if protecao_adequada:
            dogs_with_diagonal_protection += 1
        em_risco = False
        for move in onca_moves:
            if len(move) == 3 and move[2] == 'salto_consecutivo':
                caminho = move[0]
                for i in range(len(caminho) - 1):
                    l1, c1 = caminho[i]
                    l2, c2 = caminho[i + 1]
                    ml, mc = (l1 + l2) // 2, (c1 + c2) // 2
                    if (ml, mc) == (dl, dc):
                        em_risco = True
                        break
            elif len(move) >=3 and move[2] and move[2] == (dl, dc):
                em_risco = True
                break
        if em_risco:
            dogs_at_risk += 1
        suporte = 0
        suporte_diagonal = 0
        for ddl, ddc in [(-1,0), (1,0), (0,-1), (0,1)]:
            nl, nc = dl + ddl, dc + ddc
            if pos_valida(nl, nc) and get_cell(board, nl, nc) == 'c':
                suporte += 1
        for ddl, ddc in [(-1,-1), (-1,1), (1,-1), (1,1)]:
            nl, nc = dl + ddl, dc + ddc
            if pos_valida(nl, nc) and get_cell(board, nl, nc) == 'c':
                suporte += 1
                suporte_diagonal += 1
        if suporte >= 3:
            dogs_with_support += 1
        elif suporte == 0:
            dogs_isolated += 1

    if dogs_positions:
        avg_l = sum(dl for dl, dc in dogs_positions) / len(dogs_positions)
        avg_c = sum(dc for dl, dc in dogs_positions) / len(dogs_positions)
        dispersao = sum(abs(dl - avg_l) + abs(dc - avg_c) for dl, dc in dogs_positions)
        formacao = -dispersao
        if dispersao < 8:
            formacao += 200
        linha_media = avg_l
        if 3.0 <= linha_media <= 4.5:
            formacao += 50
    else:
        formacao = 0

    diagonal_chain_score = 0
    for dl, dc in dogs_positions:
        protecoes = 0
        for ddl, ddc in [(-1,-1), (-1,1), (1,-1), (1,1)]:
            nl, nc = dl + ddl, dc + ddc
            if pos_valida(nl, nc) and get_cell(board, nl, nc) == 'c':
                protecoes += 1
        diagonal_chain_score += protecoes * 10

    line_control = 0
    for linha in [2, 3, 4]:
        dogs_in_line = sum(1 for dl, dc in dogs_positions if dl == linha)
        line_control += dogs_in_line * (5 - abs(linha - 3))

    center_control = 0
    for dl, dc in dogs_positions:
        if dc == 3:
            center_control += 10
        elif dc in [2, 4]:
            center_control += 5

    wall_formation = 0
    for linha in range(2, 6):
        dogs_in_line = sum(1 for dl, dc in dogs_positions if dl == linha)
        if dogs_in_line >= 3:
            wall_formation += 20 * dogs_in_line

    prevent_retreat = 0
    if ol <= 3:
        prevent_retreat = (4 - ol) * 30

    escape_routes = 0
    for dl in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dl == 0 and dc == 0:
                continue
            nl, nc = ol + dl, oc + dc
            if pos_valida(nl, nc) and get_cell(board, nl, nc) == '-':
                has_blocker = False
                for ddl, ddc in [(-1,0), (1,0), (0,-1), (0,1)]:
                    bl, bc = nl + ddl, nc + ddc
                    if pos_valida(bl, bc) and get_cell(board, bl, bc) == 'c':
                        has_blocker = True
                        break
                if not has_blocker:
                    escape_routes += 1

    block_score = -escape_routes
    center_dist = abs(ol - 4) + abs(oc - 3)
    centrality = max(0, 6 - center_dist)
    dogs_advancement = sum(dl for dl, dc in dogs_positions)
    from utils import RECENT_BOARDS as RB
    key = board_to_key(board)
    repeat_count = RB.count(key)
    repeat_penalty = W_REPEAT * repeat_count
    randomness = random.uniform(-W_RANDOMNESS, W_RANDOMNESS)

    score = 0
    score += captured * W_CAPTURE
    score += len(onca_moves) * W_ONCA_MOB
    score += capturas_disponiveis * W_ONCA_CAPTURE
    score += centrality * W_CENTER
    score += dogs_at_risk * W_DOG_SAFETY
    score += dogs_diagonal_risk * W_DOG_DIAGONAL_RISK
    score += diagonais_expostas_total * W_DOG_DIAGONAL_EXPOSED
    score += total_diagonal_vulnerability * W_DIAGONAL_VULNERABILITY
    score += dogs_isolated * (W_DOG_SAFETY * 0.8)
    score += dogs_with_support * W_DOG_SUPPORT
    score += dogs_with_diagonal_protection * W_DIAGONAL_SUPPORT
    score += formacao * W_DOG_FORMATION
    score += block_score * W_BLOCK_ESCAPE
    score += (14 - len(onca_moves)) * W_ENCIRCLE
    score += dogs_advancement * W_DOG_ADVANCE
    score += diagonal_chain_score * W_DIAGONAL_CHAIN
    score += line_control * W_LINE_CONTROL
    score += center_control * W_CENTER_CONTROL
    score += wall_formation * W_WALL_FORMATION
    score += prevent_retreat * W_PREVENT_RETREAT
    score += repeat_penalty
    score += randomness
    if lado_atual == 'c':
        score = -score
    return score
