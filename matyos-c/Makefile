# MatyOS-C — a from-scratch C reimplementation of the MatyOS proof assistant.
#
# Needs a C11 compiler. If you don't have one, the self-contained zig toolchain
# works (pip install ziglang):
#     make CC="python -m ziglang cc"
CC     ?= cc
CFLAGS ?= -std=c11 -O2 -Wall -Wextra
SRC    := $(wildcard src/*.c)
LIBSRC := $(filter-out src/main.c, $(SRC))   # kernel/front-end, no CLI entry point

.PHONY: all test bin clean
all: test bin

build:
	mkdir -p build

# the matyos-c CLI
bin: build $(SRC)
	$(CC) $(CFLAGS) $(SRC) -o build/matyos-c

test: build $(LIBSRC) $(wildcard test/*.c)
	$(CC) $(CFLAGS) $(LIBSRC) test/test_term.c -o build/test_term
	./build/test_term
	$(CC) $(CFLAGS) $(LIBSRC) test/test_infer.c -o build/test_infer
	./build/test_infer
	$(CC) $(CFLAGS) $(LIBSRC) test/test_inductive.c -o build/test_inductive
	./build/test_inductive
	$(CC) $(CFLAGS) $(LIBSRC) test/test_equality.c -o build/test_equality
	./build/test_equality
	$(CC) $(CFLAGS) $(LIBSRC) test/test_parse.c -o build/test_parse
	./build/test_parse
	$(CC) $(CFLAGS) $(LIBSRC) test/test_science.c -o build/test_science
	./build/test_science
	$(CC) $(CFLAGS) $(LIBSRC) test/test_tactics.c -o build/test_tactics
	./build/test_tactics
	$(CC) $(CFLAGS) $(LIBSRC) test/test_project.c -o build/test_project
	./build/test_project

clean:
	rm -rf build
