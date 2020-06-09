#ifndef HELPERS_H
#define HELPERS_H

__attribute__((unused)) static inline void cdelay(int i) {
	while(i > 0) {
		__asm__ volatile("nop");
		i--;
	}
}

#endif /* HELPERS_H */
