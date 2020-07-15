#ifndef DFII_H
#define DFII_H

#include <stdbool.h>

#define DFII_CONTROL_SEL (1 << 0)
#define DFII_CONTROL_CKE (1 << 1)
#define DFII_CONTROL_ODT (1 << 2)
#define DFII_CONTROL_RESET_N (1 << 3)

#define DFII_COMMAND_CS (1 << 0)
#define DFII_COMMAND_WE (1 << 1)
#define DFII_COMMAND_CAS (1 << 2)
#define DFII_COMMAND_RAS (1 << 3)
#define DFII_COMMAND_WRDATA (1 << 4)

void dfii_setsw(struct gramCtx *ctx, bool software_control);
void dfii_initseq(struct gramCtx *ctx);
void dfii_set_p0_address(struct gramCtx *ctx, uint32_t val);
void dfii_set_p0_baddress(struct gramCtx *ctx, uint32_t val);
void dfii_p0_command(struct gramCtx *ctx, uint32_t cmd);

#endif /* DFII_H */
