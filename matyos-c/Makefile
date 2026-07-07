# MatyOS-C — a from-scratch C reimplementation of the MatyOS proof assistant.
#
# Needs a C11 compiler. If you don't have one, the self-contained zig toolchain
# works (pip install ziglang):
#     make CC="python -m ziglang cc"
CC     ?= cc
CFLAGS ?= -std=c11 -O2 -Wall -Wextra
SRC    := $(wildcard src/*.c)

.PHONY: all test clean
all: test

build:
	mkdir -p build

test: build $(SRC) $(wildcard test/*.c)
	$(CC) $(CFLAGS) $(SRC) test/test_term.c -o build/test_term
	./build/test_term

clean:
	rm -rf build
