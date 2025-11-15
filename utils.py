from collections import deque
RECENT_STATES_MAX = 10
RECENT_BOARDS = deque(maxlen=RECENT_STATES_MAX)

def board_to_key(board):
    return ''.join(''.join(row) for row in board)

def parse_board_from_lines(lines):
    board_lines = [l for l in lines if l.startswith("#")]
    if not board_lines:
        return None
    return [list(line) for line in board_lines]

def find_all_pieces(board, piece, pos_valida, get_cell):
    positions = []
    for l in range(1, 8):
        for c in range(1, 6):
            if pos_valida(l, c) and get_cell(board, l, c) == piece:
                positions.append((l, c))
    return positions

def count_pieces(board, pos_valida, get_cell):
    onca = len(find_all_pieces(board, 'o', pos_valida, get_cell))
    cachorros = len(find_all_pieces(board, 'c', pos_valida, get_cell))
    return onca, cachorros
