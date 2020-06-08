#include <gram.h>

int gram_init(void) {
#ifdef CSR_DDRCTRL_BASE
	ddrctrl_init_done_write(0);
	ddrctrl_init_error_write(0);
#endif

	sdrsw();
	init_sequence();

#ifdef CSR_DDRPHY_BASE
#ifdef DDRPHY_CMD_DELAY
	ddrphy_cdly(DDRPHY_CMD_DELAY);
#endif
#if CSR_DDRPHY_EN_VTC_ADDR
	ddrphy_en_vtc_write(0);
#endif
#if defined(SDRAM_PHY_WRITE_LEVELING_CAPABLE) || defined(SDRAM_PHY_READ_LEVELING_CAPABLE)
	sdrlevel();
#endif
#if CSR_DDRPHY_EN_VTC_ADDR
	ddrphy_en_vtc_write(1);
#endif
#endif
	sdrhw();

	if(!memtest()) {
#ifdef CSR_DDRCTRL_BASE
		ddrctrl_init_done_write(1);
		ddrctrl_init_error_write(1);
#endif
		return GRAM_ERR_MEMTEST;
	}
#ifdef CSR_DDRCTRL_BASE
	ddrctrl_init_done_write(1);
#endif

	return GRAM_ERR_NONE;
}
