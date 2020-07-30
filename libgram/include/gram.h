#ifndef GRAM_H
#define GRAM_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

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
	void *user_data;
};

struct gramProfile {
	uint8_t rdly_p0;
	uint8_t rdly_p1;
	uint32_t mode_registers[4];
};

extern __attribute__((visibility ("default"))) int gram_init(struct gramCtx *ctx, const struct gramProfile *profile, void *ddr_base, void *core_base, void *phy_base);
extern __attribute__((visibility ("default"))) int gram_generate_calibration(const struct gramCtx *ctx, struct gramProfile *profile);
extern __attribute__((visibility ("default"))) void gram_load_calibration(const struct gramCtx *ctx, const struct gramProfile *profile);

extern __attribute__((visibility ("default"))) void gram_reset_burstdet(const struct gramCtx *ctx);
extern __attribute__((visibility ("default"))) bool gram_read_burstdet(const struct gramCtx *ctx, int phase);

#ifdef GRAM_RW_FUNC
extern uint32_t gram_read(struct gramCtx *ctx, void *addr);
extern int gram_write(struct gramCtx *ctx, void *addr, uint32_t value);
#endif /* GRAM_RW_FUNC */

#endif /* GRAM_H */
