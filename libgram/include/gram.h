#ifndef GRAM_H
#define GRAM_H

enum GramError {
	GRAM_ERR_NONE = 0,
	GRAM_ERR_UNDOCUMENTED,
	GRAM_ERR_MEMTEST,
};

struct gramCoreRegs;
struct gramPHYRegs;
struct gramCtx {
	volatile void *ddr_base;
	volatile struct gramCoreRegs *core;
	volatile struct gramPHYRegs *phy;
};

extern __attribute__((visibility ("default"))) int gram_init(struct gramCtx *ctx, void *ddr_base, void *core_base, void *phy_base);
extern __attribute__((visibility ("default"))) int gram_memtest(struct gramCtx *ctx);

#endif /* GRAM_H */
