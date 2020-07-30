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

void gram_reset_burstdet(const struct gramCtx *ctx) {
#ifdef GRAM_RW_FUNC
	gram_write(ctx, &(ctx->phy->burstdet), 0);
#else
	ctx->phy->burstdet = 0;
#endif
}

bool gram_read_burstdet(const struct gramCtx *ctx, int phase) {
#ifdef GRAM_RW_FUNC
	return !!(gram_read(ctx, &(ctx->phy->burstdet)) & (1 << phase));
#else
	return !!(ctx->phy->burstdet & (1 << phase));
#endif
}

int gram_generate_calibration(const struct gramCtx *ctx, struct gramProfile *profile) {
	unsigned char rdly;
	unsigned char min_rdly_p0, min_rdly_p1;
	unsigned char max_rdly_p0 = 7, max_rdly_p1 = 7;
	uint32_t tmp;
	volatile uint32_t *ram = ctx->ddr_base;
	size_t i;

	dfii_setsw(ctx, true);

	// Find minimal rdly
	for (rdly = 0; rdly < 8; rdly++) {
		profile->rdly_p0 = rdly;
		gram_load_calibration(ctx, profile);
		gram_reset_burstdet(ctx);

		for (i = 0; i < 128; i++) {
			tmp = ram[i];
		}

		if (gram_read_burstdet(&ctx, 0)) {
			min_rdly_p0 = rdly;
			break;
		}
	}

	for (rdly = 0; rdly < 8; rdly++) {
		profile->rdly_p1 = rdly;
		gram_load_calibration(ctx, profile);
		gram_reset_burstdet(ctx);

		for (i = 0; i < 128; i++) {
			tmp = ram[i];
		}

		if (gram_read_burstdet(&ctx, 1)) {
			min_rdly_p1 = rdly;
			break;
		}
	}

	// Find maximal rdly
	for (rdly = min_rdly_p0; rdly < 8; rdly++) {
		profile->rdly_p0 = rdly;
		gram_load_calibration(ctx, profile);
		gram_reset_burstdet(ctx);

		for (i = 0; i < 128; i++) {
			tmp = ram[i];
		}

		if (!gram_read_burstdet(&ctx, 0)) {
			max_rdly_p0 = rdly - 1;
			break;
		}
	}

	for (rdly = 0; rdly < 8; rdly++) {
		profile->rdly_p1 = rdly;
		gram_load_calibration(ctx, profile);
		gram_reset_burstdet(ctx);

		for (i = 0; i < 128; i++) {
			tmp = ram[i];
		}

		if (!gram_read_burstdet(&ctx, 1)) {
			max_rdly_p1 = rdly - 1;
			break;
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
