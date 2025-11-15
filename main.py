import argparse
from conexao_tabuleiro import conecta, recebe_raw, envia_raw
from utils import parse_board_from_lines, RECENT_BOARDS, board_to_key
from movimentos import gerar_movimentos
from minimax import minimax, format_move

MAX_PROF = 4

def parse_message(msg: str):
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
    board = parse_board_from_lines(msg.splitlines())
    return meu_lado, lado_jogou, tipo_movimento, board

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("lado", choices=["o", "c"])
    parser.add_argument("-ip", default="127.0.0.1")
    parser.add_argument("-porta", default="10001")
    args = parser.parse_args()
    argv = [b"python", args.lado.encode(), args.ip.encode(), args.porta.encode()]
    conecta(argv)
    jogada_count = 0
    while True:
        msg = recebe_raw()
        if not msg:
            continue
        meu_lado, lado_jogou, tipo_movimento, board = parse_message(msg)
        if not board:
            continue
        if meu_lado != args.lado:
            continue
        jogada_count += 1
        print(f"jogada {jogada_count}")
        moves = gerar_movimentos(board, args.lado)
        if not moves:
            cmd = f"{args.lado} n\n\n"
            print(cmd.strip())
            envia_raw(cmd)
            continue
        val, mov = minimax(board, MAX_PROF, args.lado == 'o')
        if mov:
            cmd = format_move(mov, args.lado)
            print(cmd.strip())
            envia_raw(cmd)
            RECENT_BOARDS.append(board_to_key(board))
        else:
            cmd = f"{args.lado} n\n\n"
            print(cmd.strip())
            envia_raw(cmd)

if __name__ == '__main__':
    main()
