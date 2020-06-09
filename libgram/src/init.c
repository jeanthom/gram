#include <gram.h>
#include "dfii.h"

int gram_init(struct gramCtx *ctx, void *ddr_base, void *core_base, void *phy_base) {
	ctx->ddr_base = ddr_base;
	ctx->core = core_base;
	ctx->phy = phy_base;

	dfii_setsw(ctx, true);
	dfii_initseq(ctx);
	dfii_setsw(ctx, false);
}