def pos_valida(l, c):
    if l < 1 or l > 7 or c < 1 or c > 5:
        return False
    if l == 6 and (c == 1 or c == 5):
        return False
    if l == 7 and (c == 2 or c == 4):
        return False
    return True

def get_cell(board, l, c):
    if l < 0 or l >= len(board) or c < 0 or c >= len(board[0]):
        return '#'
    return board[l][c]

def set_cell(board, l, c, value):
    if l < 0 or l >= len(board) or c < 0 or c >= len(board[0]):
        return
    board[l][c] = value

def mov_possivel(tipo, lo, co, ld, cd):
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

def find_all_pieces_local(board, piece):
    positions = []
    for l in range(1, 8):
        for c in range(1, 6):
            if pos_valida(l, c) and get_cell(board, l, c) == piece:
                positions.append((l, c))
    return positions

def gerar_movimentos_cachorro(board):
    moves = []
    dogs = find_all_pieces_local(board, 'c')
    for l, c in dogs:
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
    if caminho_atual is None:
        caminho_atual = [(l, c)]
    if capturados is None:
        capturados = set()
    caminhos = []
    jumps = [(-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (-2, 2), (2, -2), (2, 2)]
    for dl, dc in jumps:
        ld, cd = l + dl, c + dc
        ml, mc = l + dl // 2, c + dc // 2
        if not pos_valida(ld, cd):
            continue
        if not pos_valida(ml, mc):
            continue
        if get_cell(board, ml, mc) != 'c':
            continue
        if get_cell(board, ld, cd) != '-':
            continue
        if (ml, mc) in capturados:
            continue
        if not mov_possivel('s', l, c, ld, cd):
            continue
        novo_board = [linha[:] for linha in board]
        set_cell(novo_board, ml, mc, '-')
        set_cell(novo_board, l, c, '-')
        set_cell(novo_board, ld, cd, 'o')
        novos_capturados = capturados | {(ml, mc)}
        novo_caminho = caminho_atual + [(ld, cd)]
        subcaminhos = gerar_saltos_consecutivos(novo_board, ld, cd, novo_caminho, novos_capturados)
        if subcaminhos:
            caminhos.extend(subcaminhos)
        else:
            caminhos.append(novo_caminho)
    if l == 7:
        for dc in [-4, 4]:
            cd = c + dc
            mc = c + dc // 2
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
            novo_board = [linha[:] for linha in board]
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
    moves = []
    onca_pos = find_all_pieces_local(board, 'o')
    if not onca_pos:
        return moves
    l, c = onca_pos[0]
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
    caminhos = gerar_saltos_consecutivos(board, l, c)
    for caminho in caminhos:
        if len(caminho) > 1:
            moves.append((caminho, None, 'salto_consecutivo'))
    return moves

def gerar_movimentos(board, lado):
    if lado == 'c':
        return gerar_movimentos_cachorro(board)
    else:
        return gerar_movimentos_onca(board)

def aplicar_movimento(board, mov):
    b2 = [linha[:] for linha in board]
    if len(mov) == 3 and mov[2] == 'salto_consecutivo':
        caminho = mov[0]
        l_inicio, c_inicio = caminho[0]
        set_cell(b2, l_inicio, c_inicio, '-')
        for i in range(len(caminho) - 1):
            l1, c1 = caminho[i]
            l2, c2 = caminho[i + 1]
            ml = (l1 + l2) // 2
            mc = (c1 + c2) // 2
            set_cell(b2, ml, mc, '-')
        l_final, c_final = caminho[-1]
        set_cell(b2, l_final, c_final, 'o')
    else:
        (l1, c1), (l2, c2), captura = mov
        peca = get_cell(b2, l1, c1)
        set_cell(b2, l2, c2, peca)
        set_cell(b2, l1, c1, '-')
        if captura:
            cl, cc = captura
            set_cell(b2, cl, cc, '-')
    return b2
