#ifndef GRAM_H
#define GRAM_H

#include <stdint.h>

enum GramError {
	GRAM_ERR_NONE = 0,
	GRAM_ERR_UNDOCUMENTED,
	GRAM_ERR_MEMTEST,
};

enum GramWidth {
	GRAM_8B,
	GRAM_32B,
}

struct gramCoreRegs;
struct gramPHYRegs;
struct gramCtx {
	volatile void *ddr_base;
	volatile struct gramCoreRegs *core;
	volatile struct gramPHYRegs *phy;
	void *user_data;
};

extern __attribute__((visibility ("default"))) int gram_init(struct gramCtx *ctx, void *ddr_base, void *core_base, void *phy_base);
extern __attribute__((visibility ("default"))) int gram_memtest(struct gramCtx *ctx);

#ifdef GRAM_RW_FUNC
extern uint32_t gram_read(struct gramCtx *ctx, void *addr);
extern int gram_write(struct gramCtx *ctx, void *addr, uint32_t value);
#endif /* GRAM_RW_FUNC */

#endif /* GRAM_H */
