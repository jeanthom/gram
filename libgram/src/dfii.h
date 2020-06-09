#ifndef DFII_H
#define DFII_H

#include <stdbool.h>

#define DFII_CONTROL_SEL (1 << 1)
#define DFII_CONTROL_CKE (1 << 2)
#define DFII_CONTROL_ODT (1 << 3)
#define DFII_CONTROL_RESET_N (1 << 4)

#define DFII_COMMAND_CS (1 << 1)
#define DFII_COMMAND_WE (1 << 2)
#define DFII_COMMAND_CAS (1 << 3)
#define DFII_COMMAND_RAS (1 << 4)
#define DFII_COMMAND_WRDATA (1 << 5)

void dfii_setsw(struct gramCtx *ctx, bool software_control);
void dfii_initseq(struct gramCtx *ctx);

#endif /* DFII_H */
