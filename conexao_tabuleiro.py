import ctypes

BUF_SIZE = 2048

# .so para linux .dll para windows
lib = ctypes.CDLL("./libtabuleiro.so")
# lib = ctypes.CDLL("./tabuleiro.dll")

lib.tabuleiro_conecta.argtypes = (ctypes.c_int, ctypes.POINTER(ctypes.c_char_p))
lib.tabuleiro_conecta.restype = None
lib.tabuleiro_envia.argtypes = (ctypes.c_char_p,)
lib.tabuleiro_envia.restype = None
lib.tabuleiro_recebe.argtypes = (ctypes.c_char_p,)
lib.tabuleiro_recebe.restype = None

def conecta(argv):
    c_argv = (ctypes.c_char_p * len(argv))(*argv)
    lib.tabuleiro_conecta(len(argv), c_argv)

def recebe_raw():
    buf = ctypes.create_string_buffer(BUF_SIZE)
    lib.tabuleiro_recebe(buf)
    return buf.value.decode(errors="ignore")

def envia_raw(cmd: str):
    lib.tabuleiro_envia(cmd.encode())
