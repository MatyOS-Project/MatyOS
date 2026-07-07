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
	$(CC) $(CFLAGS) $(SRC) test/test_infer.c -o build/test_infer
	./build/test_infer
	$(CC) $(CFLAGS) $(SRC) test/test_inductive.c -o build/test_inductive
	./build/test_inductive
	$(CC) $(CFLAGS) $(SRC) test/test_equality.c -o build/test_equality
	./build/test_equality

clean:
	rm -rf build
