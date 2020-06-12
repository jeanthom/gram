#include <stdlib.h>
#include <stdint.h>
#include <gram.h>

static inline uint32_t read32(const void *addr)
{
	return *(volatile uint32_t *)addr;
}

static inline void write32(void *addr, uint32_t value)
{
	*(volatile uint32_t *)addr = value;
}

struct uart_regs {
	uint32_t divisor;
	uint32_t rx_data;
	uint32_t rx_rdy;
	uint32_t rx_err;
	uint32_t tx_data;
	uint32_t tx_rdy;
	uint32_t zero0; // reserved
	uint32_t zero1; // reserved
	uint32_t ev_status;
	uint32_t ev_pending;
	uint32_t ev_enable;
};

void uart_write(char c)
{
	struct uart_regs *regs = 0x5000;
	while (!read32(&regs->tx_rdy));
	write32(&regs->tx_data, c);
}

void uart_writestr(const char *c) {
	while (*c) {
		uart_write(*c);
		c++;
	}
}

void memcpy(void *dest, void *src, size_t n) {
   int i;
   //cast src and dest to char*
   char *src_char = (char *)src;
   char *dest_char = (char *)dest;
   for (i=0; i<n; i++)
      dest_char[i] = src_char[i]; //copy contents byte by byte
}

void uart_writeuint32(uint32_t val) {
	const char lut[] = { '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D', 'E', 'F' };
	uint8_t *val_arr = &val;
	size_t i;

	for (i = 0; i < 4; i++) {
		uart_write(lut[(val_arr[3-i] >> 4) & 0xF]);
		uart_write(lut[val_arr[3-i] & 0xF]);
	}
}

void isr(void) {

}

int main(void) {
	uart_writestr("Firmware launched...\n");

	uart_writestr("DRAM init... ");
	struct gramCtx ctx;
	gram_init(&ctx, (void*)0x10000000, (void*)0x00009000, (void*)0x00008000);
	uart_writestr("done\n");

	uart_writestr("DRAM test... \n");
	volatile uint32_t *ram = 0x10000000;
	for (size_t i = 0; i < 1000; i++) {
		uart_writestr("Writing to 0x");
		uart_writeuint32(&ram[i]);
		uart_write('\n');
		ram[i] = 0xDEADBEEF;
	}

	for (size_t i = 0; i < 1000; i++) {
		if (ram[i] != 0xDEADBEEF) {
			uart_writestr("fail : *(0x");
			uart_writeuint32(&ram[i]);
			uart_writestr(") = ");
			uart_writeuint32(ram[i]);
			uart_write('\n');
		}
	}
	uart_writestr("done\n");

	while (1);

	return 0;
}