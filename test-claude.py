import ctypes
import argparse
import math
import copy
import random
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
MAX_PROF = 4

RECENT_STATES_MAX = 10
RECENT_BOARDS = deque(maxlen=RECENT_STATES_MAX)

# --- MAPEAMENTO DE COORDENADAS ---
def pos_valida(l, c):
    """Verifica se posição é válida (mesma lógica do controlador.c)"""
    if l < 1 or l > 7 or c < 1 or c > 5:
        return False
    if l == 6 and (c == 1 or c == 5):
        return False
    if l == 7 and (c == 2 or c == 4):
        return False
    return True

def get_cell(board, l, c):
    """Obtém célula do board usando coordenadas do controlador (1-based)"""
    if l < 0 or l >= len(board) or c < 0 or c >= len(board[0]):
        return '#'
    return board[l][c]

def set_cell(board, l, c, value):
    """Define célula do board usando coordenadas do controlador"""
    if l < 0 or l >= len(board) or c < 0 or c >= len(board[0]):
        return
    board[l][c] = value

# --- VALIDAÇÃO DE MOVIMENTOS (baseada no controlador.c) ---
def mov_possivel(tipo, lo, co, ld, cd):
    """Valida movimento exatamente como o controlador C"""
    if not pos_valida(lo, co):
        return False
    if not pos_valida(ld, cd):
        return False
    
    distl = abs(lo - ld)
    distc = abs(co - cd)
    
    if (distl + distc) == 0:
        return False
    
    if tipo == 'm':
        if lo == 7 and distl == 0:
            return distc == 2
        
        if distl > 1 or distc > 1:
            return False
        
        if ((lo + co) % 2) and ((distl + distc) > 1):
            return False
        
        if lo == 5 and ld == 6 and co != 3:
            return False
        
        if lo == 6 and (co % 2) == 0:
            if ld == 5 and cd != 3:
                return False
            if ld == 7 and cd == 3:
                return False
        
        return True
    
    elif tipo == 's':
        if lo == 7 and distl == 0:
            return distc == 4
        
        if distl == 1 or distc == 1 or (distl + distc) > 4:
            return False
        
        if ((lo + co) % 2) and ((distl + distc) > 2):
            return False
        
        if lo == 5 and ld == 7 and co != 3:
            return False
        
        if lo == 6 and ld == 4 and (
            ((co == 2) and (cd != 4)) or ((co == 4) and (cd != 2))
        ):
            return False
        
        if lo == 7 and cd != 3:
            return False
        
        return True
    
    return False

# --- PARSEAMENTO DO TABULEIRO ---
def parse_board_from_server(msg: str):
    """Extrai o tabuleiro ASCII do servidor"""
    lines = msg.splitlines()
    board_lines = [l for l in lines if l.startswith("#")]
    if not board_lines:
        return None
    
    board = []
    for line in board_lines:
        board.append(list(line))
    
    return board

def board_to_key(board):
    """Converte board para string única"""
    return ''.join(''.join(row) for row in board)

def find_all_pieces(board, piece):
    """Encontra todas as ocorrências de uma peça"""
    positions = []
    for l in range(1, 8):
        for c in range(1, 6):
            if pos_valida(l, c) and get_cell(board, l, c) == piece:
                positions.append((l, c))
    return positions

def count_pieces(board):
    """Conta peças no tabuleiro"""
    onca = len(find_all_pieces(board, 'o'))
    cachorros = len(find_all_pieces(board, 'c'))
    return onca, cachorros

# --- GERAÇÃO DE MOVIMENTOS ---
def gerar_movimentos_cachorro(board):
    """
    Gera movimentos válidos para cachorros.
    CORREÇÃO: Cachorros só podem se mover para FRENTE (linha maior) ou LATERALMENTE.
    """
    moves = []
    dogs = find_all_pieces(board, 'c')
    
    for l, c in dogs:
        # Cachorros só podem mover para frente (l+1) ou lateralmente (mesma linha)
        # Movimentos possíveis: (1,0), (0,-1), (0,1), (1,-1), (1,1)
        for dl, dc in [(1, 0), (0, -1), (0, 1), (1, -1), (1, 1)]:
            ld, cd = l + dl, c + dc
            
            if not pos_valida(ld, cd):
                continue
            
            if get_cell(board, ld, cd) != '-':
                continue
            
            if mov_possivel('m', l, c, ld, cd):
                moves.append(((l, c), (ld, cd), None))
    
    return moves

def gerar_saltos_consecutivos(board, l, c, caminho_atual=None, capturados=None):
    """
    Gera recursivamente todos os caminhos de saltos consecutivos possíveis
    para a onça a partir da posição (l, c).
    Retorna uma lista de caminhos, onde cada caminho é uma lista de posições [(l0,c0), (l1,c1), ...]
    """
    if caminho_atual is None:
        caminho_atual = [(l, c)]
    if capturados is None:
        capturados = set()

    caminhos = []
    tem_salto = False

    # Direções de salto básicas (saltos de 2 células: captura peça no meio)
    jumps = [(-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (-2, 2), (2, -2), (2, 2)]

    for dl, dc in jumps:
        ld, cd = l + dl, c + dc
        ml, mc = l + dl // 2, c + dc // 2  # posição do cachorro a ser capturado

        if not pos_valida(ld, cd):
            continue
        if not pos_valida(ml, mc):
            continue

        # exige que haja um cachorro no meio e célula de pouso vazia
        if get_cell(board, ml, mc) != 'c':
            continue
        if get_cell(board, ld, cd) != '-':
            continue
        # não recapturar a mesma peça no mesmo caminho
        if (ml, mc) in capturados:
            continue
        # mov_possivel checa regras específicas do tabuleiro (usa 's' para salto)
        if not mov_possivel('s', l, c, ld, cd):
            continue

        tem_salto = True

        # Aplica salto numa cópia do tabuleiro
        novo_board = copy.deepcopy(board)
        set_cell(novo_board, ml, mc, '-')  # remove cachorro capturado
        set_cell(novo_board, l, c, '-')    # remove onça da posição inicial
        set_cell(novo_board, ld, cd, 'o')  # coloca onça na posição de destino

        novos_capturados = capturados | {(ml, mc)}
        novo_caminho = caminho_atual + [(ld, cd)]

        # recursão: buscar saltos adicionais a partir da nova posição
        subcaminhos = gerar_saltos_consecutivos(novo_board, ld, cd, novo_caminho, novos_capturados)

        if subcaminhos:
            caminhos.extend(subcaminhos)
        else:
            # nenhum salto adicional – caminho termina aqui
            caminhos.append(novo_caminho)

    # Caso especial: linha 7 (saltos horizontais de 4 colunas, conforme lógica anterior)
    if l == 7:
        for dc in [-4, 4]:
            cd = c + dc
            mc = c + dc // 2  # capturado fica no meio (coluna média)

            if not pos_valida(7, cd):
                continue
            if not pos_valida(7, mc):
                continue

            if get_cell(board, 7, mc) != 'c':
                continue
            if get_cell(board, 7, cd) != '-':
                continue
            if (7, mc) in capturados:
                continue
            if not mov_possivel('s', 7, c, 7, cd):
                continue

            tem_salto = True

            novo_board = copy.deepcopy(board)
            set_cell(novo_board, 7, mc, '-')
            set_cell(novo_board, 7, c, '-')
            set_cell(novo_board, 7, cd, 'o')

            novos_capturados = capturados | {(7, mc)}
            novo_caminho = caminho_atual + [(7, cd)]

            subcaminhos = gerar_saltos_consecutivos(novo_board, 7, cd, novo_caminho, novos_capturados)

            if subcaminhos:
                caminhos.extend(subcaminhos)
            else:
                caminhos.append(novo_caminho)

    return caminhos

def gerar_movimentos_onca(board):
    """
    Gera movimentos válidos para a onça.
    CORREÇÃO: Implementa saltos consecutivos corretamente.
    """
    moves = []
    onca_pos = find_all_pieces(board, 'o')
    
    if not onca_pos:
        return moves
    
    l, c = onca_pos[0]
    
    # Movimento simples
    for dl in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dl == 0 and dc == 0:
                continue
            
            ld, cd = l + dl, c + dc
            
            if not pos_valida(ld, cd):
                continue
            
            if get_cell(board, ld, cd) == '-':
                if mov_possivel('m', l, c, ld, cd):
                    moves.append(((l, c), (ld, cd), None))
    
    # Saltos consecutivos
    caminhos = gerar_saltos_consecutivos(board, l, c)
    
    for caminho in caminhos:
        if len(caminho) > 1:
            # caminho é [(l1,c1), (l2,c2), (l3,c3), ...]
            # Precisamos converter para o formato esperado
            moves.append((caminho, None, 'salto_consecutivo'))
    
    return moves

def gerar_movimentos(board, lado):
    """Gera todos os movimentos válidos para um lado"""
    if lado == 'c':
        return gerar_movimentos_cachorro(board)
    else:
        return gerar_movimentos_onca(board)

def aplicar_movimento(board, mov):
    """Aplica um movimento e retorna novo tabuleiro"""
    b2 = copy.deepcopy(board)
    
    # Verifica se é um salto consecutivo
    if len(mov) == 3 and mov[2] == 'salto_consecutivo':
        caminho = mov[0]
        l_inicio, c_inicio = caminho[0]
        
        # Remove a onça da posição inicial
        set_cell(b2, l_inicio, c_inicio, '-')
        
        # Processa cada salto no caminho
        for i in range(len(caminho) - 1):
            l1, c1 = caminho[i]
            l2, c2 = caminho[i + 1]
            
            # Calcula posição do cachorro capturado
            ml = (l1 + l2) // 2
            mc = (c1 + c2) // 2
            
            # Remove o cachorro
            set_cell(b2, ml, mc, '-')
        
        # Coloca a onça na posição final
        l_final, c_final = caminho[-1]
        set_cell(b2, l_final, c_final, 'o')
    
    else:
        # Movimento simples (cachorro ou onça)
        (l1, c1), (l2, c2), captura = mov
        
        peca = get_cell(b2, l1, c1)
        set_cell(b2, l2, c2, peca)
        set_cell(b2, l1, c1, '-')
        
        if captura:
            cl, cc = captura
            set_cell(b2, cl, cc, '-')
    
    return b2

# --- NOVA FUNÇÃO: ANÁLISE DETALHADA DE VULNERABILIDADES DIAGONAIS ---
def analisar_vulnerabilidade_diagonal(board, dl, dc, onca_pos):
    """
    Analisa em detalhes a vulnerabilidade diagonal de um cachorro.
    Retorna uma tupla (risco_total, diagonais_expostas, tem_protecao_adequada)
    """
    ol, oc = onca_pos
    risco_total = 0
    diagonais_expostas = []
    tem_protecao = {(-1, -1): False, (-1, 1): False, (1, -1): False, (1, 1): False}
    
    # Verifica cada diagonal
    for dir_l, dir_c in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
        # Posição de pouso após o salto
        pouso_l, pouso_c = dl + dir_l, dc + dir_c
        # Posição onde a onça precisa estar para saltar
        onca_l, onca_c = dl - dir_l, dc - dir_c
        
        if not pos_valida(pouso_l, pouso_c) or not pos_valida(onca_l, onca_c):
            continue
        
        # Se há espaço vazio atrás E a célula de origem está livre ou ocupada pela onça
        tem_espaco_pouso = get_cell(board, pouso_l, pouso_c) == '-'
        onca_pode_estar = get_cell(board, onca_l, onca_c) in ['-', 'o']
        
        if tem_espaco_pouso and onca_pode_estar:
            # Calcula distância da onça até posição de ataque
            dist_onca = abs(ol - onca_l) + abs(oc - onca_c)
            
            # Verifica se há cachorro protegendo a diagonal (na posição de pouso)
            cachorro_protegendo = get_cell(board, pouso_l, pouso_c) == 'c'
            
            # Verifica se há cachorro adjacente na diagonal protegendo
            cachorro_adj_diagonal = False
            for check_l, check_c in [(dl + dir_l, dc), (dl, dc + dir_c)]:
                if pos_valida(check_l, check_c) and get_cell(board, check_l, check_c) == 'c':
                    cachorro_adj_diagonal = True
                    break
            
            tem_protecao[(dir_l, dir_c)] = cachorro_protegendo or cachorro_adj_diagonal
            
            if not (cachorro_protegendo or cachorro_adj_diagonal):
                diagonais_expostas.append((dir_l, dir_c))
                
                # Calcula risco baseado na distância da onça
                if dist_onca == 0:  # Onça já está em posição de ataque
                    risco_total += 1000
                elif dist_onca <= 1:  # Onça a 1 movimento de distância
                    risco_total += 500
                elif dist_onca <= 2:  # Onça a 2 movimentos
                    risco_total += 200
                elif dist_onca <= 3:  # Onça próxima
                    risco_total += 50
    
    tem_protecao_adequada = sum(tem_protecao.values()) >= 2  # Pelo menos 2 diagonais protegidas
    
    return risco_total, diagonais_expostas, tem_protecao_adequada

# --- HEURÍSTICA ULTRA MELHORADA ---
def avaliar(board, lado_atual):
    """Heurística ultra melhorada com foco máximo em proteção diagonal"""
    
    # Pesos para onça
    W_CAPTURE = 2000000
    W_ONCA_MOB = 25
    W_ONCA_CAPTURE = 150
    W_CENTER = 5
    
    # PESOS CRÍTICOS PARA CACHORROS - FOCO EM DIAGONAIS
    W_DOG_SAFETY = -1500              # Aumentado ainda mais
    W_DOG_DIAGONAL_RISK = -2000       # CRÍTICO: Risco diagonal massivo
    W_DOG_DIAGONAL_EXPOSED = -1800    # NOVO: Penalidade por diagonal exposta
    W_DIAGONAL_VULNERABILITY = -1500  # NOVO: Vulnerabilidade diagonal geral
    W_DOG_FORMATION = -500            
    W_ENCIRCLE = -200              
    W_DOG_SUPPORT = -180           
    W_DIAGONAL_SUPPORT = -400         # AUMENTADO: Suporte diagonal é VITAL
    W_BLOCK_ESCAPE = -250          
    W_DOG_ADVANCE = -8             
    W_LINE_CONTROL = -150          
    W_CENTER_CONTROL = -200        
    W_WALL_FORMATION = -150           # Aumentado
    W_PREVENT_RETREAT = -300       
    W_TIGHT_FORMATION = -350          # NOVO: Formação compacta
    W_DIAGONAL_CHAIN = -300           # NOVO: Cadeia diagonal de proteção
    W_SAFE_ADVANCE = -100             # NOVO: Avanço seguro
    
    W_REPEAT = -1000000
    W_RANDOMNESS = 20
    
    onca, cachorros = count_pieces(board)
    captured = 14 - cachorros
    
    onca_pos = find_all_pieces(board, 'o')
    if not onca_pos:
        return -99999 if lado_atual == 'o' else 99999
    
    ol, oc = onca_pos[0]
    
    onca_moves = gerar_movimentos_onca(board)
    dog_moves = gerar_movimentos_cachorro(board)
    
    # Conta capturas disponíveis (incluindo saltos consecutivos)
    capturas_disponiveis = 0
    for m in onca_moves:
        if len(m) == 3 and m[2] == 'salto_consecutivo':
            caminho = m[0]
            capturas_disponiveis += len(caminho) - 1
        elif m[2] is not None:
            capturas_disponiveis += 1
    
    dogs_positions = find_all_pieces(board, 'c')
    dogs_at_risk = 0
    dogs_with_support = 0
    dogs_isolated = 0
    dogs_diagonal_risk = 0
    total_diagonal_vulnerability = 0
    diagonais_expostas_total = 0
    dogs_with_diagonal_protection = 0
    
    # ANÁLISE DETALHADA DE CADA CACHORRO
    for dl, dc in dogs_positions:
        em_risco = False
        em_risco_diagonal = False
        
        # ANÁLISE DE VULNERABILIDADE DIAGONAL DETALHADA
        risco_diag, diagonais_exp, protecao_adequada = analisar_vulnerabilidade_diagonal(
            board, dl, dc, (ol, oc)
        )
        
        total_diagonal_vulnerability += risco_diag
        diagonais_expostas_total += len(diagonais_exp)
        
        if protecao_adequada:
            dogs_with_diagonal_protection += 1
        
        # Verifica se está em risco por movimentos da onça
        for move in onca_moves:
            if len(move) == 3 and move[2] == 'salto_consecutivo':
                caminho = move[0]
                for i in range(len(caminho) - 1):
                    l1, c1 = caminho[i]
                    l2, c2 = caminho[i + 1]
                    ml, mc = (l1 + l2) // 2, (c1 + c2) // 2
                    if (ml, mc) == (dl, dc):
                        em_risco = True
                        # Verifica se é captura diagonal
                        if abs(l1 - l2) == 2 and abs(c1 - c2) == 2:
                            em_risco_diagonal = True
                            dogs_diagonal_risk += 1
                        break
            elif move[2] and move[2] == (dl, dc):
                em_risco = True
                break
        
        if em_risco:
            dogs_at_risk += 1
        
        # Conta suporte (ortogonal e diagonal)
        suporte = 0
        suporte_diagonal = 0
        
        # Suporte ortogonal
        for ddl, ddc in [(-1,0), (1,0), (0,-1), (0,1)]:
            nl, nc = dl + ddl, dc + ddc
            if pos_valida(nl, nc) and get_cell(board, nl, nc) == 'c':
                suporte += 1
        
        # Suporte diagonal (CRUCIAL)
        for ddl, ddc in [(-1,-1), (-1,1), (1,-1), (1,1)]:
            nl, nc = dl + ddl, dc + ddc
            if pos_valida(nl, nc) and get_cell(board, nl, nc) == 'c':
                suporte += 1
                suporte_diagonal += 1
        
        if suporte >= 3:  # Aumentado de 2 para 3
            dogs_with_support += 1
        elif suporte == 0:
            dogs_isolated += 1
    
    # FORMAÇÃO - Prefere cachorros agrupados
    if dogs_positions:
        avg_l = sum(dl for dl, dc in dogs_positions) / len(dogs_positions)
        avg_c = sum(dc for dl, dc in dogs_positions) / len(dogs_positions)
        
        # Penaliza dispersão
        dispersao = sum(abs(dl - avg_l) + abs(dc - avg_c) for dl, dc in dogs_positions)
        formacao = -dispersao
        
        # Bônus para formação compacta (baixa dispersão)
        if dispersao < 8:
            formacao += 200
        
        # Bônus para linha média estratégica
        linha_media = avg_l
        if 3.0 <= linha_media <= 4.5:
            formacao += 50
    else:
        formacao = 0
    
    # CADEIA DIAGONAL - Cachorros protegendo uns aos outros em diagonal
    diagonal_chain_score = 0
    for dl, dc in dogs_positions:
        protecoes = 0
        for ddl, ddc in [(-1,-1), (-1,1), (1,-1), (1,1)]:
            nl, nc = dl + ddl, dc + ddc
            if pos_valida(nl, nc) and get_cell(board, nl, nc) == 'c':
                protecoes += 1
        diagonal_chain_score += protecoes * 10
    
    # Controle de linhas estratégicas
    line_control = 0
    for linha in [2, 3, 4]:
        dogs_in_line = sum(1 for dl, dc in dogs_positions if dl == linha)
        line_control += dogs_in_line * (5 - abs(linha - 3))
    
    # Controle do centro
    center_control = 0
    for dl, dc in dogs_positions:
        if dc == 3:
            center_control += 10
        elif dc in [2, 4]:
            center_control += 5
    
    # Formação de parede
    wall_formation = 0
    for linha in range(2, 6):
        dogs_in_line = sum(1 for dl, dc in dogs_positions if dl == linha)
        if dogs_in_line >= 3:
            wall_formation += 20 * dogs_in_line
    
    # Prevenir recuo da onça
    prevent_retreat = 0
    if ol <= 3:
        prevent_retreat = (4 - ol) * 30
    
    # Rotas de fuga da onça
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
    
    # Centralidade da onça
    center_dist = abs(ol - 4) + abs(oc - 3)
    centrality = max(0, 6 - center_dist)
    
    # Avanço dos cachorros
    dogs_advancement = sum(dl for dl, dc in dogs_positions)
    
    # Penalidade por repetição
    key = board_to_key(board)
    repeat_count = RECENT_BOARDS.count(key)
    repeat_penalty = W_REPEAT * repeat_count
    
    # Aleatoriedade mínima
    randomness = random.uniform(-W_RANDOMNESS, W_RANDOMNESS)
    
    # CÁLCULO FINAL DO SCORE
    score = 0
    
    # Fatores da onça
    score += captured * W_CAPTURE
    score += len(onca_moves) * W_ONCA_MOB
    score += capturas_disponiveis * W_ONCA_CAPTURE
    score += centrality * W_CENTER
    
    # Fatores dos cachorros (ULTRA MELHORADOS)
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
    
    # Outros fatores
    score += line_control * W_LINE_CONTROL
    score += center_control * W_CENTER_CONTROL
    score += wall_formation * W_WALL_FORMATION
    score += prevent_retreat * W_PREVENT_RETREAT
    
    # Penalidades e aleatoriedade
    score += repeat_penalty
    score += randomness
    
    if lado_atual == 'c':
        score = -score
    
    return score

# --- MINIMAX COM AVALIAÇÃO MELHORADA ---
def minimax(board, prof, maximizando, alpha=-math.inf, beta=math.inf, path_history=None):
    """Minimax com poda alpha-beta e avaliação melhorada de segurança"""
    
    if path_history is None:
        path_history = []
    
    current_key = board_to_key(board)
    
    if path_history.count(current_key) >= 2:
        return -50000 if maximizando else 50000, None
    
    onca, cachorros = count_pieces(board)
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
        
        # Prioriza saltos consecutivos
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
            """
            Avalia a segurança de um movimento de cachorro com FOCO MÁXIMO em diagonais.
            Retorna tupla para ordenação (valores menores = movimentos mais seguros)
            """
            (l1, c1), (l2, c2), _ = mov
            nb = aplicar_movimento(board, mov)
            nb_key = board_to_key(nb)
            repeticoes = new_path.count(nb_key)
            
            # ANÁLISE CRÍTICA DE VULNERABILIDADE DIAGONAL
            onca_pos = find_all_pieces(nb, 'o')
            if onca_pos:
                risco_diag, diagonais_exp, protecao_ok = analisar_vulnerabilidade_diagonal(
                    nb, l2, c2, onca_pos[0]
                )
            else:
                risco_diag, diagonais_exp, protecao_ok = 0, [], True
            
            # Normaliza risco diagonal para ordenação
            risco_diagonal_normalizado = len(diagonais_exp) + (0 if protecao_ok else 2)
            vulnerabilidade_diagonal = risco_diag / 100.0  # Escala para comparação
            
            # Verifica se o cachorro ficará em risco imediato após o movimento
            onca_moves_after = gerar_movimentos_onca(nb)
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
                            # Verifica se é captura diagonal
                            if abs(caminho[i][0] - caminho[i+1][0]) == 2 and \
                               abs(caminho[i][1] - caminho[i+1][1]) == 2:
                                em_risco_diagonal_imediato = True
                            break
                elif m[2] == (l2, c2):
                    em_risco_imediato = True
                    capturas_possiveis += 1
                    break
            
            # Conta suporte na posição destino (ortogonal + diagonal)
            suporte_total = 0
            suporte_diagonal = 0
            
            for dl, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                nl, nc = l2 + dl, c2 + dc
                if pos_valida(nl, nc) and get_cell(nb, nl, nc) == 'c':
                    suporte_total += 1
            
            # SUPORTE DIAGONAL É CRÍTICO
            for dl, dc in [(-1,-1), (-1,1), (1,-1), (1,1)]:
                nl, nc = l2 + dl, c2 + dc
                if pos_valida(nl, nc) and get_cell(nb, nl, nc) == 'c':
                    suporte_total += 1
                    suporte_diagonal += 1
            
            # Penaliza movimentos para trás
            movimento_para_tras = 1 if l2 < l1 else 0
            
            # Favorece movimentos para linhas estratégicas
            bonus_linha = 0
            if l2 in [3, 4]:
                bonus_linha = -1
            
            # Verifica isolamento na posição destino
            isolamento = 1 if suporte_total == 0 else 0
            
            # Verifica se o movimento cria formação compacta
            dogs_positions = find_all_pieces(nb, 'c')
            if dogs_positions:
                avg_l = sum(dl for dl, dc in dogs_positions) / len(dogs_positions)
                avg_c = sum(dc for dl, dc in dogs_positions) / len(dogs_positions)
                dist_centro_grupo = abs(l2 - avg_l) + abs(c2 - avg_c)
            else:
                dist_centro_grupo = 0
            
            # Verifica proteção mútua diagonal (muito importante)
            cadeia_diagonal = suporte_diagonal >= 2
            
            # PRIORIDADE DE CRITÉRIOS (ordem importa!):
            # 1. Não repetir posições
            # 2. Evitar risco diagonal imediato
            # 3. Evitar risco imediato geral
            # 4. Minimizar vulnerabilidade diagonal
            # 5. Maximizar suporte diagonal
            # 6. Evitar isolamento
            # 7. Não mover para trás
            # 8. Manter formação compacta
            
            noise = random.random() * 0.01  # Ruído mínimo para desempate
            
            return (
                repeticoes * 1000,                          # 1º: Evita repetição (crítico)
                em_risco_diagonal_imediato * 900,           # 2º: Risco diagonal imediato
                em_risco_imediato * 800,                    # 3º: Risco imediato geral
                capturas_possiveis * 700,                   # 4º: Número de capturas possíveis
                risco_diagonal_normalizado * 600,           # 5º: Vulnerabilidade diagonal
                vulnerabilidade_diagonal,                   # 6º: Risco diagonal quantitativo
                -suporte_diagonal * 50,                     # 7º: Maximiza suporte diagonal
                -suporte_total * 30,                        # 8º: Maximiza suporte total
                isolamento * 400,                           # 9º: Evita isolamento
                movimento_para_tras * 200,                  # 10º: Evita retrocesso
                dist_centro_grupo * 10,                     # 11º: Mantém formação
                -cadeia_diagonal * 100,                     # 12º: Favorece cadeia diagonal
                bonus_linha,                                # 13º: Linhas estratégicas
                noise                                       # 14º: Aleatoriedade mínima
            )
        
        # ORDENA MOVIMENTOS POR SEGURANÇA (mais seguros primeiro)
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
    """Formata movimento para enviar ao controlador"""
    
    # Verifica se é salto consecutivo
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

# --- LOOP PRINCIPAL ---
def parse_message(msg):
    """Extrai informações da mensagem"""
    lines = [l.strip() for l in msg.splitlines() if l.strip()]
    
    if not lines:
        return None, None, None, None
    
    meu_lado = lines[0][0] if len(lines[0]) > 0 else None
    
    lado_jogou = None
    tipo_movimento = None
    if len(lines) > 1 and ' ' in lines[1]:
        partes = lines[1].split()
        if len(partes) >= 2:
            lado_jogou = partes[0]
            tipo_movimento = partes[1]
    
    board_lines = [l for l in msg.splitlines() if l.startswith("#")]
    board = None
    if board_lines:
        board = [list(line) for line in board_lines]
    
    return meu_lado, lado_jogou, tipo_movimento, board

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

    print(f"🎮 Jogando como: {args.lado.upper()}")
    print(f"🧠 Profundidade: {MAX_PROF}")
    if args.lado == 'c':
        print("🛡️  MODO DEFENSIVO DIAGONAL ATIVADO")
    print("="*50)

    jogada_count = 0

    while True:
        print(f"\n⏳ Aguardando mensagem do servidor...")
        lib.tabuleiro_recebe(buf)
        msg = buf.value.decode(errors="ignore")
        
        if not msg:
            continue
        
        print("\n" + "="*50)
        print("📨 MENSAGEM DO SERVIDOR:")
        print(msg)
        print("="*50)
        
        meu_lado, lado_jogou, tipo_movimento, board = parse_message(msg)
        
        if not board:
            print("⚠️ Não foi possível extrair o tabuleiro")
            continue
        
        print(f"\n📋 Análise da mensagem:")
        print(f"   • Próximo a jogar: {meu_lado}")
        print(f"   • Último que jogou: {lado_jogou} (tipo: {tipo_movimento})")
        print(f"   • Meu lado: {args.lado}")
        
        if meu_lado != args.lado:
            print(f"\n⏸️ NÃO é minha vez")
            continue
        
        print(f"\n✅ CONFIRMADO: É minha vez de jogar!")
        jogada_count += 1
        print(f"🎯 Jogada #{jogada_count}")
        
        moves = gerar_movimentos(board, args.lado)
        print(f"📊 Movimentos disponíveis: {len(moves)}")
        
        if args.lado == 'o':
            saltos = [m for m in moves if len(m) == 3 and m[2] == 'salto_consecutivo']
            print(f"🎯 Saltos consecutivos disponíveis: {len(saltos)}")
        else:
            # Análise de segurança para cachorros
            onca_pos = find_all_pieces(board, 'o')
            if onca_pos:
                dogs = find_all_pieces(board, 'c')
                em_risco = 0
                for dl, dc in dogs:
                    risco, diag_exp, _ = analisar_vulnerabilidade_diagonal(board, dl, dc, onca_pos[0])
                    if len(diag_exp) > 0:
                        em_risco += 1
                print(f"⚠️  Cachorros em risco diagonal: {em_risco}/{len(dogs)}")
        
        if not moves:
            print("❌ Sem movimentos possíveis")
            cmd = f"{args.lado} n\n"
            print(f"📤 Enviando movimento nulo: {cmd.strip()}")
            lib.tabuleiro_envia(cmd.encode())
            continue
        
        print(f"\n🤔 Calculando melhor jogada (profundidade {MAX_PROF})...")
        val, mov = minimax(board, MAX_PROF, args.lado == 'o')
        
        if mov:
            cmd = format_move(mov, args.lado)
            
            if len(mov) == 3 and mov[2] == 'salto_consecutivo':
                caminho = mov[0]
                print(f"\n🎯 SALTO CONSECUTIVO")
                print(f"   Caminho: {' → '.join([f'({l},{c})' for l, c in caminho])}")
                print(f"   Capturas: {len(caminho) - 1}")
            else:
                (l1, c1), (l2, c2), captura = mov
                tipo = "🎯 CAPTURA" if captura else "➡️ MOVIMENTO"
                print(f"\n{tipo}")
                print(f"   De: ({l1},{c1}) → Para: ({l2},{c2})")
                
                # Análise de segurança do movimento (para cachorros)
                if args.lado == 'c':
                    nb = aplicar_movimento(board, mov)
                    onca_pos = find_all_pieces(nb, 'o')
                    if onca_pos:
                        risco, diag_exp, protecao = analisar_vulnerabilidade_diagonal(
                            nb, l2, c2, onca_pos[0]
                        )
                        print(f"   🛡️  Diagonais expostas: {len(diag_exp)}/4")
                        print(f"   {'✅' if protecao else '⚠️ '} Proteção adequada: {'Sim' if protecao else 'Não'}")
            
            print(f"   Score: {val}")
            print(f"   Comando: {cmd.strip()}")
            
            print(f"\n📤 Enviando movimento...")
            lib.tabuleiro_envia(cmd.encode())
            print(f"✅ Movimento enviado com sucesso!")
            
            key = board_to_key(board)
            RECENT_BOARDS.append(key)
        else:
            print("❌ Minimax não encontrou movimento")
            cmd = f"{args.lado} n\n"
            print(f"📤 Enviando movimento nulo: {cmd.strip()}")
            lib.tabuleiro_envia(cmd.encode())

if __name__ == "__main__":
    main()