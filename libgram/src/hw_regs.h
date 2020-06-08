#ifndef HW_REGS_H
#define HW_REGS_H

struct ECP5PHY {
	uint32_t dly_sel;
	uint32_t rdly_dq_rst;
	uint32_t rdly_dq_inc;
	uint32_t rdly_dq_bitslip_rst;
	uint32_t rdly_dq_bitslip;
	uint32_t burstdet_clr;
	uint32_t burstdet_seen;
} __attribute__((packed));

struct DFII_Phase {
	uint32_t command;
	uint32_t command_issue;
	uint32_t address;
	uint32_t baddress;
	uint32_t wrdata;
	uint32_t rddata;
} __attribute__((packed));

struct DFII {
	uint32_t control;

} __attribute__((packed));

#endif /* HW_REGS_H */