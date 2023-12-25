OBJS := src/init.o src/dfii.o src/calibration.o

TRIPLE :=

CC := $(TRIPLE)gcc
AS := $(TRIPLE)as
OBJCOPY := $(TRIPLE)objcopy
AR := $(TRIPLE)ar
LD := $(TRIPLE)ld

CFLAGS += -fvisibility=hidden -nostdlib -O0 -g -Iinclude -std=c99 -Wall -Wno-error -pedantic -DGRAM_RW_FUNC
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
