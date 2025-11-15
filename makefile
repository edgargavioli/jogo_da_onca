CFLAGS = -g -Wall -Wno-unused-result -O3
LDLIBS = -l hiredis -l readline

all: controlador exemplo1 exemplo2

controlador: controlador.c

exemplo1: tabuleiro.h tabuleiro.c exemplo1.c

exemplo2: tabuleiro.h tabuleiro.c exemplo2.c

clean:
	rm -f controlador exemplo1 exemplo2
