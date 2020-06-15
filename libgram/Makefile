OBJS := src/init.o src/memtest.o src/dfii.o

TRIPLE := riscv64-unknown-elf-

CC := $(TRIPLE)gcc
AS := $(TRIPLE)as
OBJCOPY := $(TRIPLE)objcopy
AR := $(TRIPLE)ar
LD := $(TRIPLE)ld

CFLAGS  := -fvisibility=hidden -march=rv32i -mabi=ilp32 -nostdlib -Os -Iinclude
LDFLAGS := -melf32lriscv -nostdlib

all: libgram.a

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

libgram.a: $(OBJS)
	$(LD) $(LDFLAGS) -r $(OBJS) -o libgram.o
	$(OBJCOPY) --localize-hidden libgram.o libgram.clean.o
	$(AR) -rcs $@ libgram.clean.o

clean:
	rm -rf $(OBJS)
	rm -f libgram.a
	rm -f libgram.o
	rm -f libgram.clean.o
.PHONY: clean
