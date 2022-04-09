#include <stdint.h>

#include "hw_regs.h"
#include <gram.h>
#include "dfii.h"
#include "helpers.h"

static void dfii_setcontrol(const struct gramCtx *ctx, uint8_t val) {
#ifdef GRAM_RW_FUNC
	gram_write(ctx, (void*)&(ctx->core->control), val);
#else
	ctx->core->control = val;
#endif
}

void dfii_setsw(const struct gramCtx *ctx, bool software_control) {
	if (software_control) {
		dfii_setcontrol(ctx, DFII_CONTROL_CKE|DFII_CONTROL_ODT|DFII_CONTROL_RESET|DFII_COMMAND_CS);
	} else {
		dfii_setcontrol(ctx, DFII_CONTROL_SEL|DFII_CONTROL_RESET);
	}
}

void dfii_set_p0_address(const struct gramCtx *ctx, uint32_t val) {
#ifdef GRAM_RW_FUNC
	gram_write(ctx, (void*)&(ctx->core->phases[0].address), val);
#else
	ctx->core->phases[0].address = val;
#endif
}

void dfii_set_p0_baddress(const struct gramCtx *ctx, uint32_t val) {
#ifdef GRAM_RW_FUNC
	gram_write(ctx, (void*)&(ctx->core->phases[0].baddress), val);
#else
	ctx->core->phases[0].baddress = val;
#endif
}

void dfii_p0_command(const struct gramCtx *ctx, uint32_t cmd) {
#ifdef GRAM_RW_FUNC
	gram_write(ctx, (void*)&(ctx->core->phases[0].command), cmd);
	gram_write(ctx, (void*)&(ctx->core->phases[0].command_issue), 1);
#else
	ctx->core->phases[0].command = cmd;
	ctx->core->phases[0].command_issue = 1;
#endif
}

/* Set MRx register */
static void dfii_set_mr(const struct gramCtx *ctx, uint8_t mr, uint16_t val) {
	dfii_set_p0_address(ctx, val);
	dfii_set_p0_baddress(ctx, mr);
	dfii_p0_command(ctx, DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS);
}

#define MR0_DLL_RESET (1 << 8)
void dfii_initseq(const struct gramCtx *ctx, const struct gramProfile *profile) {
	/* Assert reset */
	dfii_set_p0_address(ctx, 0x0);
	dfii_set_p0_baddress(ctx, 0);
	dfii_setcontrol(ctx, 0);
	cdelay(50000);

	/* Release reset */
	dfii_set_p0_address(ctx, 0x0);
	dfii_set_p0_baddress(ctx, 0);
	dfii_setcontrol(ctx, DFII_CONTROL_ODT|DFII_CONTROL_RESET);
	cdelay(50000);

	/* Bring CKE high */
	dfii_set_p0_address(ctx, 0x0);
	dfii_set_p0_baddress(ctx, 0);
	dfii_setcontrol(ctx, DFII_CONTROL_CKE|DFII_CONTROL_ODT|DFII_CONTROL_RESET);
	cdelay(10000);

	/* Load Mode Register 2, CWL=5 */
	dfii_set_mr(ctx, 2, profile->mode_registers[2]);

	/* Load Mode Register 3 */
	dfii_set_mr(ctx, 3, profile->mode_registers[3]);

	/* Load Mode Register 1 */
	dfii_set_mr(ctx, 1, profile->mode_registers[1]);

	/* Load Mode Register 0, CL=6, BL=8 */
	dfii_set_mr(ctx, 0, profile->mode_registers[0]);
    if (profile->mode_registers[0] & MR0_DLL_RESET) {
	   cdelay(100);
	   dfii_set_mr(ctx, 0, profile->mode_registers[0] & ~MR0_DLL_RESET);
    }
	cdelay(600);

	/* ZQ Calibration */
	dfii_set_p0_address(ctx, 0x400);
	dfii_set_p0_baddress(ctx, 0);
	dfii_p0_command(ctx, DFII_COMMAND_WE|DFII_COMMAND_CS);
	cdelay(600);
}
