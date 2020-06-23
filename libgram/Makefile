OBJS := src/init.o src/memtest.o src/dfii.o

TRIPLE := riscv64-unknown-elf-

CC := $(TRIPLE)gcc
AS := $(TRIPLE)as
OBJCOPY := $(TRIPLE)objcopy
AR := $(TRIPLE)ar
LD := $(TRIPLE)ld

CFLAGS += -fvisibility=hidden -nostdlib -Os -Iinclude -std=c99
LDFLAGS += -nostdlib

ifeq ($(TRIPLE),riscv64-unknown-elf-)
CFLAGS += -march=rv32i -mabi=ilp32
LDFLAGS += -melf32lriscv
endif

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
