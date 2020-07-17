#include <stdint.h>

#include "hw_regs.h"
#include <gram.h>
#include "dfii.h"
#include "helpers.h"

static void dfii_setcontrol(struct gramCtx *ctx, uint8_t val) {
#ifdef GRAM_RW_FUNC
	gram_write(ctx, &(ctx->core->control), val);
#else
	ctx->core->control = val;
#endif
}

void dfii_setsw(struct gramCtx *ctx, bool software_control) {
	if (software_control) {
		dfii_setcontrol(ctx, DFII_CONTROL_CKE|DFII_CONTROL_ODT|DFII_CONTROL_RESET_N);
	} else {
		dfii_setcontrol(ctx, DFII_CONTROL_SEL);
	}
}

void dfii_set_p0_address(struct gramCtx *ctx, uint32_t val) {
#ifdef GRAM_RW_FUNC
	gram_write(ctx, &(ctx->core->phases[0].address), val);
#else
	ctx->core->phases[0].address = val;
#endif
}

void dfii_set_p0_baddress(struct gramCtx *ctx, uint32_t val) {
#ifdef GRAM_RW_FUNC
	gram_write(ctx, &(ctx->core->phases[0].baddress), val);
#else
	ctx->core->phases[0].baddress = val;
#endif
}

void dfii_p0_command(struct gramCtx *ctx, uint32_t cmd) {
#ifdef GRAM_RW_FUNC
	gram_write(ctx, &(ctx->core->phases[0].command), cmd);
	gram_write(ctx, &(ctx->core->phases[0].command_issue), 1);
#else
	ctx->core->phases[0].command = cmd;
	ctx->core->phases[0].command_issue = 1;
#endif
}

/* Set MRx register */
static void dfii_set_mr(struct gramCtx *ctx, uint8_t mr, uint16_t val) {
	dfii_set_p0_address(ctx, val);
	dfii_set_p0_baddress(ctx, mr);
	dfii_p0_command(ctx, DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
}

/* TODO: those values are hardcoded for ECPIX-5's RAM */
/* Should add the capacity to generate MRx from RAM spec */
void dfii_initseq(struct gramCtx *ctx) {
	/* Release reset */
	dfii_set_p0_address(ctx, 0x0);
	dfii_set_p0_baddress(ctx, 0);
	dfii_setcontrol(ctx, DFII_CONTROL_ODT|DFII_CONTROL_RESET_N);
	cdelay(50000);

	/* Bring CKE high */
	dfii_set_p0_address(ctx, 0x0);
	dfii_set_p0_baddress(ctx, 0);
	dfii_setcontrol(ctx, DFII_CONTROL_CKE|DFII_CONTROL_ODT|DFII_CONTROL_RESET_N);
	cdelay(10000);

	/* Load Mode Register 2, CWL=5 */
	dfii_set_mr(ctx, 2, 0x200);

	/* Load Mode Register 3 */
	dfii_set_mr(ctx, 3, 0x0);

	/* Load Mode Register 1 */
	dfii_set_mr(ctx, 1, 0x6);

	/* Load Mode Register 0, CL=6, BL=8 */
	dfii_set_mr(ctx, 0, 0x320);
	cdelay(100);
	dfii_set_mr(ctx, 0, 0x220);
	cdelay(600);

	/* ZQ Calibration */
	dfii_set_p0_address(ctx, 0x400);
	dfii_set_p0_baddress(ctx, 0);
	dfii_p0_command(ctx, DFII_COMMAND_WE|DFII_COMMAND_CS);
	cdelay(600);
}
