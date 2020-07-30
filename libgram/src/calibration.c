#include <stdint.h>
#include <stdio.h>

#include "hw_regs.h"
#include <gram.h>
#include "dfii.h"
#include "helpers.h"

static void set_rdly(struct gramCtx *ctx, unsigned int phase, unsigned int rdly) {
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

void gram_reset_burstdet(struct gramCtx *ctx) {
#ifdef GRAM_RW_FUNC
	gram_write(ctx, &(ctx->phy->burstdet), 0);
#else
	ctx->phy->burstdet = 0;
#endif
}

bool gram_read_burstdet(struct gramCtx *ctx, int phase) {
#ifdef GRAM_RW_FUNC
	return gram_read(ctx, &(ctx->phy->burstdet)) & (1 << phase);
#else
	return ctx->phy->burstdet & (1 << phase);
#endif
}

int gram_generate_calibration(struct gramCtx *ctx, struct gramProfile *profile) {
	uint32_t refval[8];
	size_t i, j, k;
	int score;

	dfii_setsw(ctx, true);

	for (i = 0; i < 8; i++) {
		for (j = 0; j < 8; j++) {
			/* Generating test pattern */
			for (k = 0; k < 8; k++) {
				refval[k] = (0xABCD1234*i*j) & 0xFFFFFFFF;
			}

			/* Writing to RAM */

			/* Reading from RAM */
			score = 0;
			for (k = 0; k < 8; k++) {

			}
		}
	}

	dfii_setsw(ctx, false);

	return 0;
}

void gram_load_calibration(struct gramCtx *ctx, struct gramProfile *profile) {
	dfii_setsw(ctx, true);
	set_rdly(ctx, 0, profile->rdly_p0);
	set_rdly(ctx, 1, profile->rdly_p1);
	dfii_setsw(ctx, false);
}
