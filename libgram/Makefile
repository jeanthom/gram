OBJS := src/init.o src/memtest.o

TRIPLE := riscv64-unknown-elf

CC := $(TRIPLE)-gcc
AS := $(TRIPLE)-as
OBJCOPY := $(TRIPLE)-objcopy
AR := $(TRIPLE)-ar

CFLAGS  := -march=rv32i -mabi=ilp32 -nostdlib -Os -Iinclude
LDFLAGS := -march=rv32i -mabi=ilp32 -nostdlib

all: libgram.a

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

libgram.a: $(OBJS)
	$(AR) rcs $@ $(OBJS)

clean:
	rm -rf $(OBJS)
	rm -f libgram.a
.PHONY: clean
