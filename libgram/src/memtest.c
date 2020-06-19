#include <gram.h>

static int memtest8(struct gramCtx *ctx, size_t length) {
	volatile uint8_t *ram = (volatile uint8_t*)ctx->ddr_base;
	size_t i;

	for (i = 0; i < length; i++) {
		ram[i] = 0xDE;
	}

	for (i = 0; i < length; i++) {
		if (ram[i] != 0xDE) {
			return GRAM_ERR_MEMTEST;
		}
	}

	return GRAM_ERR_NONE;
}

static int memtest32(struct gramCtx *ctx, size_t length) {
	volatile uint32_t *ram = (volatile uint32_t*)ctx->ddr_base;
	size_t i;

	for (i = 0; i < length; i++) {
		ram[i] = 0xFEEDFACE;
	}

	for (i = 0; i < length; i++) {
		if (ram[i] != 0xFEEDFACE) {
			return GRAM_ERR_MEMTEST;
		}
	}

	return GRAM_ERR_NONE;
}

int gram_memtest(struct gramCtx *ctx, size_t length, enum GramWidth width) {
	if (width == GRAM_8B) {
		return memtest8(ctx, length);
	} else if (width == GRAM_32B) {
		return memtest32(ctx, length);
	}

	return GRAM_ERR_UNDOCUMENTED;
}
