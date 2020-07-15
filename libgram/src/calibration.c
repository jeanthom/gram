#include <stdint.h>

#include "hw_regs.h"
#include <gram.h>
#include "dfii.h"
#include "helpers.h"

static void set_dly_sel(struct gramCtx *ctx, int sel) {
#ifdef GRAM_RW_FUNC
	gram_write(ctx, &(ctx->phy->dly_sel), sel);
#else
	ctx->phy->dly_sel = sel;
#endif
}

static void rdly_dq_inc(struct gramCtx *ctx) {
#ifdef GRAM_RW_FUNC
	gram_write(ctx, &(ctx->phy->rdly_dq_inc), 1);
#else
	ctx->phy->rdly_dq_inc = 1;
#endif
}

static void rdly_dq_bitslip_inc(struct gramCtx *ctx) {
#ifdef GRAM_RW_FUNC
	gram_write(ctx, &(ctx->phy->rdly_dq_bitslip), 1);
#else
	ctx->phy->rdly_dq_bitslip = 1;
#endif
}

static void read_delay_inc(struct gramCtx *ctx, int module) {
	/* sel module */
	set_dly_sel(ctx, 1 << module);

	/* inc delay */
	rdly_dq_inc(ctx);

	/* unsel module */
	set_dly_sel(ctx, 0);

	/* Sync all DQSBUFM's, By toggling all dly_sel (DQSBUFM.PAUSE) lines. */
	set_dly_sel(ctx, 0xFF);
	set_dly_sel(ctx, 0);
}

static void bitslip_inc(struct gramCtx *ctx, int module) {
	/* sel module */
	set_dly_sel(ctx, 1 << module);

	/* inc delay */
	rdly_dq_bitslip_inc(ctx);

	/* unsel module */
	set_dly_sel(ctx, 0);

	/* Sync all DQSBUFM's, By toggling all dly_sel (DQSBUFM.PAUSE) lines. */
	set_dly_sel(ctx, 0xFF);
	set_dly_sel(ctx, 0);
}

int gram_calibration_auto(struct gramCtx *ctx) {
	dfii_setsw(ctx, true);

	// TODO: reset all delays and bitslip

	read_delay_inc(ctx, 0);
	read_delay_inc(ctx, 1);

	dfii_setsw(ctx, false);

	return 0;
}

void gram_load_calibration(void) {

}
