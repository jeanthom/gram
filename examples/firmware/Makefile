OBJS := main.o entry.o

TRIPLE := riscv64-unknown-elf

CC      := $(TRIPLE)-gcc
AS      := $(TRIPLE)-as
OBJCOPY := $(TRIPLE)-objcopy
PYTHON  := python

CFLAGS  := -march=rv32i -mabi=ilp32 -nostdlib -Os -I../../libgram/include
LDFLAGS := -march=rv32i -mabi=ilp32 -nostdlib -Tlink.ld -L../../libgram -lgram

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

%.o: %.S
	$(CC) $(CFLAGS) -c $< -o $@

main.bin: $(OBJS) link.ld ../../libgram/libgram.a
	$(CC) $(LDFLAGS) $(OBJS) ../../libgram/libgram.a -o main.elf
	$(OBJCOPY) -O binary main.elf main.bin

all: main.bin

clean:
	rm -f $(OBJS)
	rm *.elf
	rm *.bin
.PHONY: clean
