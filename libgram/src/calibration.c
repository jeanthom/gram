#include <stdint.h>
#include <stdio.h>

#include "hw_regs.h"
#include <gram.h>
#include "dfii.h"
#include "helpers.h"

static void set_rdly(const struct gramCtx *ctx, unsigned int phase, unsigned int rdly) {
#ifdef GRAM_RW_FUNC
	if (phase == 0) {
		gram_write(ctx, &(ctx->phy->rdly_p0), rdly);
	} else if (phase == 1) {
		gram_write(ctx, &(ctx->phy->rdly_p1), rdly);
	}
#else
	if (phase == 0) {
		ctx->phy->rdly_p0 = rdly;
	} else if (phase == 1) {
		ctx->phy->rdly_p1 = rdly;
	}
#endif
}

static inline uint32_t lsfr(uint32_t in) {
	return (in >> 1) ^ (uint32_t)(0 - (in & 1u) & 0xd0000001);
}

static bool memtest(uint32_t *start, uint32_t *stop, int delay) {
	const uint32_t seed = 0x6C616D62;
	uint32_t rand = seed;
	volatile uint32_t *ptr;
	int i;

	for (ptr = start; ptr < stop; ptr++) {
		*ptr = rand;
		rand = lsfr(rand);
	}

	for (i = 0; i < delay; i++) {
		__asm__("nop");
	}

	rand = seed;
	for (ptr = start; ptr < stop; ptr++) {
		if (*ptr != rand) {
			return false;
		}
		rand = lsfr(rand);
	}

	return true;
}

void gram_reset_burstdet(const struct gramCtx *ctx) {
#ifdef GRAM_RW_FUNC
	gram_write(ctx, &(ctx->phy->burstdet), 0);
#else
	ctx->phy->burstdet = 0;
#endif
}

bool gram_read_burstdet(const struct gramCtx *ctx, int phase) {
#ifdef GRAM_RW_FUNC
	return gram_read(ctx, &(ctx->phy->burstdet)) & (1 << phase);
#else
	return ctx->phy->burstdet & (1 << phase);
#endif
}

int gram_generate_calibration(const struct gramCtx *ctx, struct gramProfile *profile) {
	unsigned char rdly_p0, rdly_p1;
	unsigned char min_rdly_p0, min_rdly_p1;
	unsigned char max_rdly_p0, max_rdly_p1;

	dfii_setsw(ctx, true);

	// Find minimal rdly
	for (rdly_p0 = 0; rdly_p0 < 8; rdly_p0++) {
		for (rdly_p1 = 0; rdly_p1 < 8; rdly_p1++) {

		}
	}

	// Find maximal rdly
	for (rdly_p0 = 0; rdly_p0 < 8; rdly_p0++) {
		for (rdly_p1 = 0; rdly_p1 < 8; rdly_p1++) {

		}
	}

	dfii_setsw(ctx, false);

	// Store average rdly value
	profile->rdly_p0 = (min_rdly_p0+max_rdly_p0)/2;
	profile->rdly_p1 = (min_rdly_p1+max_rdly_p1)/2;

	return 0;
}

void gram_load_calibration(const struct gramCtx *ctx, const struct gramProfile *profile) {
	dfii_setsw(ctx, true);
	set_rdly(ctx, 0, profile->rdly_p0);
	set_rdly(ctx, 1, profile->rdly_p1);
	dfii_setsw(ctx, false);
}
