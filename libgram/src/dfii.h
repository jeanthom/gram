#ifndef DFII_H
#define DFII_H

#include <stdbool.h>

#define DFII_CONTROL_SEL (1 << 0)
#define DFII_CONTROL_CKE (1 << 1)
#define DFII_CONTROL_ODT (1 << 2)
#define DFII_CONTROL_RESET (1 << 3)

#define DFII_COMMAND_CS (1 << 0)
#define DFII_COMMAND_WE (1 << 1)
#define DFII_COMMAND_CAS (1 << 2)
#define DFII_COMMAND_RAS (1 << 3)
#define DFII_COMMAND_WRDATA (1 << 4)

void dfii_setsw(const struct gramCtx *ctx, bool software_control);
void dfii_initseq(const struct gramCtx *ctx, const struct gramProfile *profile);
void dfii_set_p0_address(const struct gramCtx *ctx, uint32_t val);
void dfii_set_p0_baddress(const struct gramCtx *ctx, uint32_t val);
void dfii_p0_command(const struct gramCtx *ctx, uint32_t cmd);

#endif /* DFII_H */
